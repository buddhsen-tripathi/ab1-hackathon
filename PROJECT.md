# BillReady Triage Desk

**Medicare Part B wound care billing triage for post-acute care facilities.**

BillReady automates the data collection and triage steps that billers currently do manually in PointClickCare (PCC). It pulls patient data from a mock PCC API, extracts wound details from clinical notes and assessments, and produces a prioritized worklist telling billers **who to act on — and why**.

---

## The Problem

Wound care billing under Medicare Part B requires:

1. An **active wound** (pressure ulcer, diabetic foot ulcer, venous ulcer, etc.)
2. **Active Medicare Part B coverage**
3. Documented measurements (length, width, depth) and drainage level

Billers today open charts one by one, read free-text notes, and decide whether a claim is ready. BillReady replaces that manual triage with an automated pipeline and a biller-first UI.

---

## How We Stand Out

Most hackathon teams will ship a generic pipeline: fetch → regex/LLM → CSV → sortable table. BillReady differentiates on four axes:

| Axis | Typical approach | BillReady |
|---|---|---|
| **Speed** | Sequential API calls, re-fetch everything | Async ingestion with semaphore, SQLite cache, incremental sync ready |
| **Extraction** | One LLM call per patient | Tiered parsers: assessment JSON → regex → prose rules → LLM only where needed (Phase 3) |
| **Output** | Engineer-facing data dump | Biller worklist with swimlanes, plain-English reasons, evidence view |
| **Trust** | Black-box routing | Auditable extraction with source attribution and highlighted note spans |

**One-line pitch:** *BillReady turns 300 PCC records into a prioritized billing worklist — with evidence, confidence, and plain-English reasons — in under 3 minutes, even with API throttling.*

---

## Routing Decisions

| Decision | Meaning |
|---|---|
| `auto_accept` | All required fields clearly documented — safe to route to billing |
| `flag_for_review` | Data ambiguous or incomplete — clinician/biller should review |
| `reject` | Not eligible (wrong payer) or extraction not reliable enough |

Each patient gets a **plain-English reason** and, for flagged cases, a **what's missing** explanation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BillReady Pipeline                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  PCC API     │───▶│  Ingestion   │───▶│  SQLite Cache    │  │
│  │  (300 pts)   │    │  async+retry │    │  api_cache       │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Tiered Extraction Engine                     │  │
│  │  ┌────────────┐ ┌────────────┐ ┌──────────┐ ┌─────────┐ │  │
│  │  │ Assessment │ │ SOAP/SPN   │ │  Prose   │ │ Multi-  │ │  │
│  │  │ JSON parse │ │ regex      │ │ patterns │ │ wound   │ │  │
│  │  └────────────┘ └────────────┘ └──────────┘ └─────────┘ │  │
│  │                         │                                 │  │
│  │                         ▼                                 │  │
│  │              Source Fusion + Confidence                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Eligibility & Routing                        │  │
│  │  • Active Medicare Part B check                           │  │
│  │  • Required field validation                              │  │
│  │  • Confidence-scored routing + plain-English reasons      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│              ┌───────────────┴───────────────┐                  │
│              ▼                               ▼                  │
│  ┌──────────────────┐          ┌──────────────────────────┐  │
│  │  eligibility.csv │          │  Streamlit Triage Desk   │  │
│  │  (backup export) │          │  swimlanes + evidence    │  │
│  └──────────────────┘          └──────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data flow

1. **Ingestion** — Fetch patients, diagnoses, coverage, notes, and assessments for all 3 facilities (300 patients). Handle 30% rate-limit (HTTP 429) with `Retry-After` backoff. Cache raw responses in SQLite.
2. **Extraction** — Parse wound fields from each source using the fastest appropriate parser. Merge note + assessment data with per-field confidence.
3. **Routing** — Check MCB eligibility, validate required fields, assign routing decision with reason.
4. **Presentation** — CSV for export; Streamlit dashboard for biller workflow.

### Two patient ID systems

| ID | Type | Used for |
|---|---|---|
| `patient_id` | string (`FA-001`) | `/diagnoses`, `/coverage` |
| `id` | integer (`1`) | `/notes`, `/assessments` |

The patients endpoint returns both; ingestion resolves the mapping.

---

## Data Formats (from API survey)

| Format | Count (approx) | Parser tier |
|---|---|---|
| Envive narrative | 135 | Text patterns + assessment fusion |
| Prose shorthand (`Meas 8.0x3.5x0.2cm`) | 118 | Prose regex |
| Multi-wound notes | 221 | Primary-wound selection |
| Nested assessment JSON | 300 | Assessment narrative parser |
| Classic SOAP labeled | 0 | Regex (ready if data appears) |

Assessments use nested `sections → questions → answer` JSON, not flat fields.

---

## Project Structure

```
ab1-hackathon/
├── PROJECT.md              # This file
├── README.md               # Hackathon challenge spec
├── API.md                  # Mock API documentation
├── run_pipeline.py         # CLI: run ingestion + routing
├── run_dashboard.py        # CLI: launch Streamlit UI
├── requirements.txt
├── billready/
│   ├── api/                # Async PCC client + ingestion
│   ├── storage/            # SQLite cache
│   ├── extraction/         # Tiered wound parsers + fusion
│   ├── eligibility/        # MCB check + routing rules
│   ├── ui/                 # Streamlit triage desk
│   └── pipeline.py         # Orchestrator
└── data/                   # Generated (gitignored)
    ├── billready.db
    └── eligibility.csv
```

---

## Build Phases

### Phase 1 — Core pipeline ✅

- [x] Async ingestion with 429 retry + SQLite cache
- [x] Assessment parser (flat + nested JSON)
- [x] SOAP / Envive / prose text extraction
- [x] Source fusion (note + assessment merge)
- [x] MCB eligibility check
- [x] Confidence-scored routing with plain-English reasons
- [x] CSV output

**Results:** 300 patients, 35 auto-accept, 79 flag-for-review, 186 reject. Cached re-run < 1s.

### Phase 2 — Biller UX + extraction polish ✅

- [x] React dashboard (replaces Streamlit)
- [x] FastAPI backend serving SQLite data
- [x] Patient expanders with inline detail
- [x] Missing-field tags + filters (depth, length, wound type, etc.)
- [x] Part B submission eligibility badges
- [x] Pipeline stats in sidebar

### Phase 3 — Demo polish

- [ ] LLM tier for hardest Envive-only cases
- [ ] Incremental sync demo (`since` parameter)
- [ ] Export auto-accept list for billing
- [ ] Presentation walkthrough script

---

## Running Locally

```bash
# Setup (once)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run pipeline (first run ~3 min, cached < 1 sec)
python run_pipeline.py

# Terminal 1 — API backend
python run_api.py

# Terminal 2 — React dashboard
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

### OpenAI (optional — for LLM verification)

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
# Restart run_api.py — the dashboard will show "OpenAI connected"
```

Use **Run pipeline → LLM verify auto-accept** in the dashboard, or CLI:

```bash
python run_pipeline.py --llm-verify
```

Legacy Streamlit UI is still available via `billready/ui/app.py` but React is the primary dashboard.

> **Note:** The repo folder name is `ab1-hackathon`. Use the full path if `cd ab1-hackathon` fails:
> `cd "/Users/.../Sundai projects/ai foundry nyc/ab1-hackathon"`

---

## Judging Alignment

| Criterion | How BillReady addresses it |
|---|---|
| **Pipeline design** | Async + retry + cache; clear module separation; stats visible |
| **Extraction accuracy** | Tiered parsers tuned to actual data formats; source fusion |
| **Schema & data modeling** | Structured eligibility output with confidence + source |
| **Presentation** | Biller worklist, not raw JSON; plain-English reasons |
| **Problem-solving** | Multi-wound handling, nested assessments, ambiguous case flagging |

---

## Related docs

- [README.md](./README.md) — official hackathon challenge
- [PROBLEM.md](./PROBLEM.md) — plain-language problem explanation
- [API.md](./API.md) — mock PCC API reference

---

## Team

Branch: `liliia` — Liliia's working branch on the shared repo.
