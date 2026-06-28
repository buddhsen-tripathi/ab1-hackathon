# Medicare Part B Wound Care Billing — Demo Guide

> **5-minute walkthrough** of the automated eligibility triage pipeline.  
> 300 synthetic patients · 3 facilities · live routing on the dashboard

---

## The Problem

Post-acute care facilities submit Medicare Part B wound care claims manually.
Billers eyeball charts, miss required fields, and claims get denied — often weeks later.
Denial rates for wound care claims average **30–40%**, most caused by missing documentation that was *in the chart all along*.

**What we built:** An automated triage pipeline that reads the chart, routes each patient, and hands billers only the cases that genuinely need human judgment.

---

## Results at a Glance

| Decision | Count | What it means |
|---|---|---|
| **Auto-Accept** | 92 | All required fields present, extraction confidence ≥ 75% — safe to bill now |
| **Flag for Review** | 49 | Something specific is missing or uncertain — actionable, fixable |
| **Reject (non-MCB)** | 155 | Not Medicare Part B — out of scope for this pipeline |
| **Reject (MCB)** | 4 | MCB patients with no wound documentation at all |

> The biller's queue just went from **145 charts → 49 cases.**
> That's a **66% reduction** in manual review work.

---

## How the Routing Works

Every patient passes through three gates in order.
A patient fails fast — if Gate 1 rejects them, Gates 2 and 3 are never evaluated.

```
Patient record
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  GATE 1 · Payer Eligibility                         │
│  payer_code == "MCB" AND coverage not expired?      │
└─────────────────────────────────────────────────────┘
     │ fail → REJECT  "Not eligible for Medicare Part B — payer: HMO"
     │ pass
     ▼
┌─────────────────────────────────────────────────────┐
│  GATE 2 · Active Wound Diagnosis (ICD-10)           │
│  Active wound ICD-10 code in problem list?          │
└─────────────────────────────────────────────────────┘
     │ no ICD-10, no wound in notes → REJECT
     │ no ICD-10, but wound in notes → FLAG  (clinician adds code)
     │ pass
     ▼
┌─────────────────────────────────────────────────────┐
│  GATE 3 · Extraction Completeness + Confidence      │
│  All required fields present? Confidence ≥ 75%?     │
└─────────────────────────────────────────────────────┘
     │ missing fields → FLAG  (specific fields named)
     │ confidence < 40% → REJECT
     │ confidence 40–74% → FLAG  (verify before billing)
     │ complete + ≥ 75% → AUTO-ACCEPT ✓
```

---

## Gate 1 · Payer Eligibility

**What we check:**
- `primary_payer_code == "MCB"` on the patient record
- Coverage `effective_to` is null (no end date) or is in the future

**Example — Instant Reject:**
> Patient FA-002 (Leon Dawson) · Payer: `HMO`
> → *"Not eligible for Medicare Part B wound care billing — payer: HMO"*
> We don't open the chart. 155 of 300 patients exit here.

**Why the coverage date check matters:**  
A patient can have MCB on file but with an expired effective date — e.g., they switched to a Medicare Advantage plan mid-year. That's still a billing rejection. Khushi's original branch checked payer code only; the combined pipeline also validates the date range.

---

## Gate 2 · Active Wound ICD-10 Diagnosis

**ICD-10 prefixes we accept:**

| Code | Condition |
|---|---|
| `L89` | Pressure ulcer |
| `E11.62` / `E10.62` | Diabetic foot ulcer (Type 1 & 2) |
| `I83` | Venous ulcer |
| `I70.2` | Arterial ulcer |
| `L02` | Abscess / cellulitis |
| `L97` | Non-pressure ulcer of lower limb |
| `L98` | Other chronic skin ulcer |
| `T20–T25` | Burns |

**Two outcomes when ICD-10 is missing:**

**Outcome A — Flag (fixable):** The wound is documented in nursing notes or an assessment, but no matching ICD-10 is in the problem list.

> Patient FA-026 (surgical site) · Measurements: 3.8 × 2.2 cm · Drainage: heavy  
> → *"Wound documented in notes but no supporting ICD-10 diagnosis on record — claim will be denied without diagnosis code. Clinician must add wound diagnosis before billing."*

This is the most valuable flag in the pipeline. The documentation exists — a clinician just needs to add one code. 8 patients fall into this bucket.

**Outcome B — Reject:** No wound in notes, no ICD-10. Nothing to work with.

> Patients FA-052, FA-109, FC-006, FC-045 all have active MCB but zero wound documentation in any note or assessment.

---

## Gate 3 · Extraction + Confidence

### Wound-Type Aware Required Fields

This is the critical clinical logic. **Required fields differ by wound type** — a one-size-fits-all checklist misroutes patients.

| Wound Type | Required Fields |
|---|---|
| **Pressure Ulcer** | type, **stage**, length, width, **depth**, drainage |
| **Diabetic / Arterial Ulcer** | type, length, width, **depth**, drainage |
| **Venous Ulcer** | type, length, width, drainage *(depth optional)* |
| **Abscess / Burn / Surgical** | type, length, width, drainage *(depth optional)* |

**Why depth is required for pressure ulcers but not venous:**  
Pressure ulcer staging (Stage 2, 3, 4, Unstageable) is determined by tissue depth — it's the billing code. Venous ulcers are superficial by definition; depth is clinically unusual to document and not required for coding.

**Example — Pressure Ulcer Missing Depth (Flag):**

> Patient FA-001 (Agnes Dunbar) · Pressure Ulcer Stage 3 · Right hip  
> Measurements: 2.9 × 2.8 cm · Drainage: heavy  
> Depth: *not documented*  
> → *"Missing required field(s): Depth. Review chart and obtain missing data before billing."*

> Patient FA-034 · Pressure Ulcer Stage 2  
> Measurements: 3.0 × 2.2 cm · Drainage: moderate · Depth: *not documented*  
> Same flag. Both are billable once a clinician measures and documents depth.

**Example — Complete Pressure Ulcer (Auto-Accept):**

> Patient FA-011 · Pressure Ulcer Stage 2 · Sacral region  
> Measurements: 1.2 × 1.5 × 0.4 cm · Drainage: light  
> Source: `assessment_structured+note_text` · Confidence: **98%**  
> → Auto-Accept ✓

**Example — Venous Ulcer, No Depth Needed (Auto-Accept):**

> Patient FA-003 · Venous Ulcer · Right lower leg  
> Measurements: 8.0 × 3.5 × 0.2 cm · Drainage: moderate  
> Source: `assessment_structured+note_multi` · Confidence: **98%**  
> → Auto-Accept ✓ *(depth present but not required — wouldn't have blocked billing without it)*

---

### Confidence Scoring

The pipeline reads **six different documentation formats** and assigns a source-specific confidence score.

| Source Format | Example | Confidence |
|---|---|---|
| `assessment_structured` | Weekly wound sheet with explicit fields | **0.98** |
| `assessment_narrative` | Long-text answer in assessment form | 0.85 × (fields / 5), min 0.88 if complete |
| `note_soap` | Labeled SOAP note: `Location:`, `Length:` | **0.95** if ≥ 4 fields |
| `note_prose` | Envive narrative: `Meas. 2.9 x 2.8 cm` | **0.90** if complete |
| `note_multi` | Multi-wound note (picks primary by size × completeness) | 0.65 × (fields / 5) |
| `note_text` | Free-text fallback | 0.60 × (fields / 5), min 0.80 if complete |

**When two sources are available, they're merged** — primary = higher confidence, secondary fills gaps. If the merged result is complete, confidence floors at 0.85.

> **In practice:** 92% of auto-accepted patients come from `assessment_structured+note_*` fusion, which yields 98% confidence. The remaining 8% come from narrative assessments (85% confidence).

**Confidence thresholds:**
- **≥ 75%** + all required fields → `auto_accept`
- **40–74%** → `flag_for_review` (verify before billing)
- **< 40%** → `reject` (data too ambiguous to act on)

---

## Flag Breakdown (49 patients)

Understanding *why* patients are flagged tells the biller what action to take:

| Root Cause | Count | Clinician Action |
|---|---|---|
| Wound type not identified | 21 | Find type in chart, update documentation |
| Missing ICD-10 diagnosis | 8 | Add active wound diagnosis code |
| Missing drainage amount | 6 | Add to next nursing assessment |
| Missing depth (pressure ulcer) | 5 | Measure and document wound depth |
| Other missing fields | 9 | Varies by case |

> **The most common flag (21 patients):** Wound type couldn't be extracted from the note. This usually means the nurse wrote "wound to sacrum" without naming it as a pressure ulcer — one word added to the note resolves it.

---

## Wound Type Breakdown (MCB patients)

| Wound Type | Auto-Accept | Flagged | Total |
|---|---|---|---|
| Diabetic foot ulcer | 24 | 3 | 27 |
| Pressure ulcer | 20 | 17 | 37 |
| Venous ulcer | 17 | 0 | 17 |
| Abscess | 16 | 0 | 16 |
| Burn | 8 | 0 | 8 |
| Arterial ulcer | 5 | 0 | 5 |
| Surgical site infection | 2 | 8 | 10 |

**Notable:** Pressure ulcers have the highest flag rate (46%) — driven by missing depth. Surgical site infections are flagged almost entirely due to missing ICD-10. Venous and abscess cases have 0% flag rate because their required field set is simpler.

---

## Audit Trail

Every routing decision is:
- **Plain English** — billers don't need to decode codes
- **Field-specific** — flags name exactly what's missing
- **Source-attributed** — every extracted value traces back to the note or assessment it came from
- **Confidence-scored** — billers know how much to trust the extraction

Click any patient in the dashboard → the detail panel shows the decision reason, all ICD-10 codes, raw note text, assessment sections, and which fields were missing.

---

## Technical Stack

```
fetch_all.py       → pulls data from PCC API (300 patients, 3 facilities)
extraction.py      → multi-format clinical note parser with confidence scoring
eligibility.py     → 3-gate routing engine
build_json.py      → assembles dashboard JSON from CSVs
dashboard/         → Next.js + shadcn/ui table with drill-down detail panel
agent_review.py    → LLM advisory annotations on flagged cases (advisory only, no auto-promotion)
```

---

*Built at the ABI Frameworks Hackathon · June 2026*
