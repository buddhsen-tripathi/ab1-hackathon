# Creative Ideas — ABI Wound-Care Billing Pipeline

Built on top of what already exists: ingestion w/ rate-limit handling, 300 patients
in SQLite, and `backend/app/characterize.py` already detecting dirty-data traps
(doubled words, laterality conflicts, multi-wound, Envive narrative blobs).

The creative layer should target the judging criteria that **aren't** about raw
accuracy: **problem-solving on ambiguous cases** and **presentation to a
non-technical biller**.

---

## Top picks (win the demo)

### 1. Cross-source reconciliation — strongest differentiator
Each patient has **two independent sources**: free-text `notes` and structured
`assessments` (`raw_json`). Cross-check them to drive the routing decision:

| Condition | Decision | Reason |
|---|---|---|
| Both sources agree on wound type + measurements | `auto_accept` | High confidence — corroborated |
| Only one source has the data | `flag_for_review` | Single-source, unverified |
| Sources **conflict** (note 3.2cm vs JSON 4.1cm; sacrum vs heel) | `flag_for_review` | **DISCREPANCY** — loud flag |
| Neither parseable | `reject` | No reliable extraction |

Turns routing from "did regex match?" into a defensible **clinical-data-integrity**
argument. Directly answers "how did you handle ambiguity / what tradeoffs?"

### 2. Evidence highlighting / provenance in the UI
Click a patient → show the raw note with extracted spans highlighted
(length / width / depth / drainage lit up in the source text), assessment `raw_json`
side-by-side. The decision is never a black box. Cheapest way to nail "explain it to
a non-technical audience."

### 3. Revenue-at-risk dollar framing
Billers think in money, not rows. Header KPIs:
> **187 auto-accept = ~$X billable now · 64 flagged = $Y at risk pending review · 49 rejected**

Rough CPT-based per-wound estimates make it land as a *business tool*, not a data dump.

---

## Strong bonus (if time)

### 4. LLM adjudicator on the flag pile only
Deterministic regex handles the easy ~80%; send **only** the ambiguous Envive
narratives to Claude with structured output → extracted fields + confidence +
one-line reasoning trace. Smart cost/accuracy tradeoff; uses the "LLM bonus."
Surface the reasoning trace in the UI.

### 5. Natural-language cohort query
"Show me Facility B diabetic foot ulcers, moderate drainage, active MCB" →
text-to-SQL over the existing DB. Great live-demo moment, low effort.

---

## Skip
- **Wound-healing trajectory over time** — only ~400 notes / 300 patients, so most
  patients have a single note. Not enough longitudinal data to be honest about it.

---

## Recommendation
**#1 + #2 + #3** as the core (reconciliation drives a smart decision; provenance +
dollars sell it), plus **#4** for the LLM bonus. The story:
**smart triage → transparent reasoning → business value.**

Highest-leverage first build: the **#1 reconciliation engine** — plugs straight into
the existing `characterize.py` + DB.
