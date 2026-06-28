# How the Pipeline Works

End-to-end walkthrough of the ABI wound-care billing pipeline — from raw,
rate-limited EHR data to a biller-ready routing decision, with a live UI and an
agentic assistant on top.

The job: given 300 synthetic PointClickCare (PCC) patients across 3 facilities,
decide which ones are billable for Medicare Part B wound care, and for each give
a decision — `auto_accept`, `flag_for_review`, or `reject` — with a plain-English
reason a biller can act on.

---

## 1. The stack

| Layer | Tech | Where |
|---|---|---|
| Backend API | FastAPI (Python) | `backend/app/main.py` |
| Storage | Neon Postgres (`psycopg3`) | `backend/app/db.py` |
| LLM | OpenRouter (`anthropic/claude-sonnet-4.6`) | `backend/app/llm.py`, `agent.py` |
| Frontend | Next.js 15 (App Router) + Tailwind v4 | `frontend/` |

Run both with one command from the repo root:

```bash
npm run setup    # first time: venv + pip + npm install
npm run dev      # backend :8000 + frontend :3000
```

---

## 2. The six stages

```
   ┌─────────┐   ┌────────┐   ┌───────┐   ┌──────────────┐   ┌─────────┐   ┌───────┐
   │ Ingest  │──▶│ Store  │──▶│ Char- │──▶│   Extract    │──▶│  Route  │──▶│Present│
   │ (PCC API)│  │ (Neon) │   │ acter-│   │ (cascade +   │   │(decision│   │ (UI + │
   │ + retry │   │        │   │ ize   │   │  LLM layer)  │   │  tree)  │   │ chat) │
   └─────────┘   └────────┘   └───────┘   └──────────────┘   └─────────┘   └───────┘
   patients/      raw JSONB    formats,    wound_extractions  patient_       dashboards
   diagnoses/     + promoted   payer mix,  (one row/wound)    eligibility    + agent
   coverage/      columns      traps                          (one row/pt)
   notes/
   assessments
```

All six run as one streamed job (`ingest.run_stream()`), or individually via
their own endpoints. Stages 1–5 are pure backend; stage 6 is the frontend.

---

## 3. Ingest — pulling from a hostile API

`backend/app/ingest.py`, `pcc_client.py`

The mock PCC API returns **HTTP 429 on ~30% of requests, independently per
request**. The insight: because failures are independent, retrying drives the
per-record failure probability to near zero —

```
P(still failing after k tries) = 0.30^k
  k=3 → 2.7%      k=6 → 0.07%      k=12 → 0.0000005%
```

So `pcc_client.get()` retries up to 12× with light jitter and **near-immediate
retry** (the 429 is random noise, not a real congestion signal, so honoring
`Retry-After` would just waste time).

Throughput comes from fanning out: the unit of parallelism is the **individual
call**, not the patient. All ~1,200 child requests (4 endpoints × 300 patients)
go into one 48-worker thread pool, so a retry on one call never blocks its
siblings. The roster (3 facility calls) runs first to discover the patients.

Two patient identifiers exist and must be used correctly:
- `patient_id` (string, `FA-001`) → `/diagnoses`, `/coverage`
- `id` (integer, `1`) → `/notes`, `/assessments`

---

## 4. Store — Neon Postgres

`backend/app/db.py`

Every record is stored twice: a few **promoted columns** for fast querying, plus
the **full raw record as JSONB** so nothing is ever lost. Upserts use
`INSERT … ON CONFLICT (id) DO UPDATE`, so re-ingestion is idempotent.

Two Neon-specific gotchas the code handles:
- The connection string is the **pooled (pgbouncer) endpoint**, which doesn't
  support server-side prepared statements → `connect()` sets `prepare_threshold=None`.
- pgbouncer drops connections left idle, and the record fetch takes ~15s. So the
  pipeline opens a **fresh short-lived connection per write** instead of holding
  one open across the run.
- Large `executemany` payloads break psycopg3's pipeline mode, so bulk writes go
  in chunks.

Tables: `patients`, `diagnoses`, `coverage`, `notes`, `assessments` (raw
ingestion) → `wound_extractions` (extract output) → `patient_eligibility` (route
output) → `kb_*` (the self-growing knowledge base).

---

## 5. Characterize — know your data before parsing it

`backend/app/characterize.py`

Profiles the ingested data so extraction is defensible: note format families
(SOAP / Envive narrative / shorthand / structured), assessment JSON shapes,
measurement completeness (L×W×D vs L×W-only), payer/coverage signal, and the
deliberate **dirty-data traps** (doubled words like "stage stage 3", laterality
conflicts, multi-wound notes). It writes nothing — it's the evidence behind the
extraction strategy.

A key subtlety it surfaces: `payer_type` lumps Medicare A/B/D all as "Medicare",
so Part B can only be confirmed via `payer_code == 'MCB'`.

---

## 6. Extract — the knowledge-base cascade + LLM layer

`backend/app/preprocess/`, `kb.py`, `llm.py`

Every source document (note or assessment) becomes one or more `WoundExtraction`
rows in a single canonical schema (`preprocess/schema.py`) — so the router can
reason over one shape regardless of source. Per document, a 4-step cascade runs,
cheapest first:

```
1. signature → cache    identical text seen before? restamp the cached result, skip everything
2. heuristic parse      regex / structured-field parsers → WoundExtraction(s), KB-normalized
3. confidence gate      low confidence OR blocking flag OR hard format? → escalate
4. LLM escalation       the model reads the RAW text, resolves fields, AND teaches the KB
```

**Method** per extraction is recorded as `structured_field`, `regex`, or `llm`.

**The confidence gate** (`llm.needs_escalation`) is what keeps the LLM cheap:
heuristics handle the confident majority for free; only documents that are
low-confidence (`< 0.75`), carry a blocking flag, or are in a hard free-text
format (Envive narrative, shorthand, unknown) escalate to the model.

**The self-growing knowledge base** (`kb.py`) is the clever part. When the LLM
resolves something — a new abbreviation (`stg` → `stage`) or synonym (`weeping` →
`light` drainage) — it's **written back** to `kb_abbreviations` / `kb_lexicon`,
so the next run handles that case deterministically and the LLM fires less over
time. Identical note text is memoized in `kb_extractions`, so re-runs are nearly
free. The KB is loaded into memory once per run (Neon is slow), parsed against
in-memory, and flushed in one batch at the end.

---

## 7. Route — the decision tree

`backend/app/eligibility/`

For each patient, the router loads coverage, the primary wound extraction(s), a
count of secondary wounds, and whether an active wound ICD-10 diagnosis exists.
Then:

**Cross-source reconciliation** (`fusion.py`) — a patient often has both a note
*and* an assessment. We pick the best extraction (by completeness, then
confidence), then **merge the top two to fill gaps** (an Envive note with no
depth + a structured assessment that has depth → complete). Crucially, when both
sources state a field and **disagree**, we don't silently merge — we record a
`*_conflict` flag (wound_type / laterality / drainage / measurement) so the case
goes to review. Corroborated-and-complete extractions get a confidence bump.

**The decision cascade** (`routing.py`), thresholds `AUTO_ACCEPT=0.75`,
`MIN_REVIEW=0.4`:

| # | Condition | Decision |
|---|---|---|
| 1 | No active Medicare Part B (`coverage.has_active_mcb`) | `reject` |
| 2 | No active wound ICD-10 diagnosis (`diagnoses.is_wound_code`) | `reject`, or `flag` if a wound is documented (clinician must add the code) |
| 3 | Incomplete fields & confidence ≥ 0.4 | `flag_for_review` (lists missing fields) |
| 4 | Incomplete fields & confidence < 0.4 | `reject` (unreliable) |
| 5 | Complete but a blocking flag (conflict / multi-wound / implausible) | `flag_for_review` (discrepancy) |
| 6 | Complete & confidence ≥ 0.75 | `auto_accept` |
| 7 | Complete & confidence < 0.75 | `flag_for_review` (low confidence) |

Every result carries a **plain-English `reason`** that names the wound, the
source, and exactly what's missing or conflicting — written for a biller, not an
engineer. Output → `patient_eligibility`.

---

## 8. Present — the frontend

`frontend/app/`

| Route | Page | Shows |
|---|---|---|
| `/` | **Pipeline** | "Run pipeline" → live progression bar + per-stage visualiser + event stream (SSE) |
| `/worklist` | **Worklist** | The biller-facing routing table (filter by decision / facility / search) |
| `/signals` | **Signals** | Triage outcome, ingestion reliability, extraction readiness, LLM observability, dirty-data traps + the agentic chat |
| `/data` | **Data** | Raw table browser (paginated, searchable) over every stored table |

Collapsible sidebar; semantic design tokens (dark/light); Phosphor icons.

---

## 9. Live streaming (SSE)

`GET /pipeline/stream` runs the whole pipeline as a generator and emits one JSON
event per Server-Sent-Event frame. The UI opens an `EventSource` and renders
progress in real time.

Event types: `pipeline_start`, `stage_start`, `roster`, `progress`,
`stage_complete`, `pipeline_complete`, `error`.
Stages, in order: `connect` → `roster` → `records` → `store` → `characterize` →
`extract` → `route`. Records progress carries the live 429 count; extract
progress carries the cascade counters (escalated / enriched).

`pipeline_start` is emitted **before** the (slow, cold-starting) Neon connect, so
the UI shows life immediately instead of a frozen screen.

---

## 10. The agentic assistant

`backend/app/agent.py`, `frontend/components/ui/agent-chat.tsx`

A chat dock on the Signals page, grounded in a **live snapshot** of the pipeline
(counts, request stats, characterization, extraction + eligibility summaries)
injected into the system prompt on every message. `POST /chat` streams the reply.

It has three capabilities:
1. **Grounded Q&A** — answers about the outcome, reliability, extraction quality,
   and traps using only snapshot numbers (says "I don't have that" otherwise).
2. **Generative dashboards** — ask it to "build/chart/visualize…" and it returns
   a fenced ` ```dashboard ` JSON spec (KPI / bar / table widgets) that the
   frontend validates and renders inline using the real components.
3. **Per-patient drill-down** — name a patient id (e.g. `FA-001`) and the backend
   pre-fetches that patient's eligibility detail + wound evidence (a lightweight
   tool) so it can explain a specific decision.

---

## 11. LLM observability

`GET /llm/observability` powers the "LLM layer" panel on Signals:
- **Config** — model + Enabled/Disabled (`LLM_ENABLED` env, default on).
- **Cascade selectivity** — from the last extract run: cache hits, parsed,
  escalated, LLM-enriched.
- **Live call stats** — calls, tokens, avg latency (thread-safe `llm.STATS`).
- **Method mix** — `regex` / `structured_field` / `llm` distribution and average
  confidence, queried from `wound_extractions` (persistent, not just last run).

---

## 12. API reference

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness |
| `GET /pipeline/stream` | Run the full pipeline, stream stage events (SSE) |
| `POST /ingest` | Ingest only (background) |
| `POST /preprocess` | Re-run Extract over stored notes/assessments |
| `POST /route` | Re-run Route over current extractions |
| `GET /stats` | Request stats + data characterization |
| `GET /extractions/summary` | Field coverage, billing-ready %, method mix, traps |
| `GET /eligibility` | Routing worklist (filterable) |
| `GET /eligibility/summary` | Decision counts, by-facility, review flags |
| `GET /eligibility/{patient_id}` | One patient's decision + wound evidence |
| `GET /llm/observability` | LLM config, cascade, call stats, method mix |
| `GET /patients` | Patient roster |
| `GET /db/tables`, `GET /db/table/{name}` | Raw table browser |
| `POST /chat` | Grounded agentic assistant (streamed) |

---

## 13. Design principles worth calling out

- **Cheapest-first cascade** — deterministic heuristics + a self-growing KB do the
  bulk; the LLM is a gated specialist that also *teaches the KB*, so cost falls
  over time.
- **Never silently overwrite** — cross-source disagreements are flagged for a
  human, not merged away.
- **Defensible decisions** — every routing call cites payer, diagnosis, and the
  exact missing/conflicting fields in plain English.
- **Observable end to end** — request stats, cascade selectivity, LLM usage, and
  data quality are all surfaced, not hidden.
- **Full fidelity** — raw JSONB is kept for every record, so nothing extraction
  decides is irreversible.
