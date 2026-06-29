# EDA Summary — ABI Hackathon

## Data Overview

| File | Rows | Notes |
|---|---|---|
| `patients.csv` | 300 | 10 cols, no nulls |
| `diagnoses.csv` | 875 | 7 cols; 836 active, 39 resolved |
| `coverage.csv` | 300 | 8 cols; all `effective_to` null (all active) |
| `notes.csv` | 474 | 12 cols; `note_label` all null (pipeline fills this) |
| `assessments.csv` | 300 | 17 cols; all `status = Complete` |

---

## Patients

- **300 total** across 3 facilities
- **Facility 101:** 120 patients (FA-001 → FA-120)
- **Facility 102:** 90 patients (FB-001 → FB-090)
- **Facility 103:** 90 patients (FC-001 → FC-090)
- **10 new admissions** across all facilities

### Payer Mix

| Payer | 101 | 102 | 103 | Total |
|---|---|---|---|---|
| MCB (Medicare Part B) | 61 (51%) | 39 (43%) | 45 (50%) | **145** |
| HMO | 27 (22%) | 18 (20%) | 18 (20%) | 63 |
| MCA (Medicare Part A) | 19 (16%) | 20 (22%) | 17 (19%) | 56 |
| MCD (Medicaid) | 13 (11%) | 13 (14%) | 10 (11%) | 36 |

**145 MCB patients** are the eligibility target population.

> Note: `payer_type` in coverage only distinguishes "Medicare" and "HMO" — use `payer_code` (MCB/MCA/MCD) to identify Part B specifically.

---

## Coverage

- Every patient has exactly 1 coverage record
- All 300 are currently active (`effective_to` is null for all)
- Coverage alone does not determine eligibility — payer code and wound documentation both required

---

## Diagnoses

- Every patient has 2–4 diagnoses (875 total rows)
- **836 active**, 39 resolved
- The 836 active diagnoses include all condition types — comorbidities like diabetes, heart failure, Alzheimer's, hypertension are the majority

### Active Wound ICD-10 Codes

| Wound Type | Count |
|---|---|
| Pressure Ulcer (L89.x) | 78 |
| Diabetic Foot Ulcer (E11.62x) | 75 |
| Arterial Ulcer (I70.2x) | 67 |
| Venous Ulcer (I83.x) | 49 |
| Abscess (L02.x) | 29 |
| Burn (T2x) | 19 |
| **Total active wound dx rows** | **317** |

### MCB Eligibility Funnel

| Segment | Count |
|---|---|
| Total MCB patients | 145 |
| MCB + active wound ICD-10 | **133** — strong candidates |
| MCB + no wound ICD-10 | **12** — flag for review / reject |
| Non-MCB with wound dx (ineligible) | 151 — filtered out |

---

## Notes

- **474 notes** across 300 patients — every patient has at least 1
- 126 patients have 1 note; 174 have 2 notes

### Note Types & Formats

| Note Type | Count | Format |
|---|---|---|
| Wound (IDT) | 126 | Envive narrative |
| Wound Care Progress Note | 123 | Envive narrative |
| Wound (SPN) | 119 | Prose / multi-wound |
| HP Skin & Wound Note | 106 | Prose / multi-wound |

**Envive format** (`*Envive Care Conference Review - V 4.0`):
```
Wound Status: Pressure Ulcer to Left buttock / Measures 5.9 cm x 4.5 cm / Stage: N/A
Drainage present - serosanguineous, heavy.
```
- Structured template, regex-friendly
- Does **not** include depth

**Prose / multi-wound format**:
```
Pt seen for wound eval. Pressure Ulcer Left buttock measures aprx 5.9 x 4.5cm, depth 1.8cm.
Heel wound also eval - L heel 3.5x2.7, 0.9cm deep, slight serous.
```
- Abbreviated free text; may describe 2 wounds (take primary/first)
- Includes depth

---

## Assessments

- **300 assessments** — one per patient, all `Complete`
- Two types: `Weekly Wound Information Sheet` (161), `HP Skin & Wound` (139)
- Structured via `raw_sections`: a list of `{sectionName, questions[{question, answer}]}`

### Key Fields Available in `raw_sections`

`Location`, `Laterality`, `Wound Type`, `Stage`, `Length (cm)`, `Width (cm)`, `Depth (cm)`, `Drainage Present`, `Drainage Type`, `Drainage Amount`, `Granulation %`, `Slough %`, `Periwound`

### Completeness of Key Assessment Fields

| Field | Filled | % |
|---|---|---|
| Wound Type | 219/300 | 73% |
| Location | 219/300 | 73% |
| Length (cm) | 219/300 | 73% |
| Width (cm) | 219/300 | 73% |
| Depth (cm) | 219/300 | 73% |
| Drainage Amount | 201/300 | 67% |
| Stage | 39/300 | 13% |

The ~27% missing structured wound data must be filled from notes.

---

## Wound Extraction Results

After merging assessments (primary) and notes (gap-fill):

| Field | Filled | % |
|---|---|---|
| wound_type | 248/300 | 83% |
| location | 271/300 | 90% |
| length_cm | 289/300 | 96% |
| width_cm | 289/300 | 96% |
| depth_cm | 237/300 | 79% |
| drainage | 248/300 | 83% |
| stage | 115/300 | 38% |

> Stage low by design — only pressure ulcers are staged. Non-pressure wound types will always be null here.

### Known Extraction Gaps
- **Depth:** Envive notes don't include depth; ~21% of patients missing this field
- **Wound type:** 52 patients (17%) have no extractable wound type — these will route to `flag_for_review` or `reject`
- **Stage cleanup needed:** some values show "N" (parsed from "N/A") rather than null

---

## Key Takeaways for Eligibility Logic

1. **Only 145 patients are MCB** — all others are immediately ineligible
2. **133 of 145 MCB patients have an active wound diagnosis** — strong signal for eligibility
3. **12 MCB patients have no wound ICD-10** — extraction from notes/assessments is their only shot
4. **Measurements are well-captured** (96%) — the main missing field is depth (Envive format limitation)
5. **Drainage and wound type** are the other fields that will drive `flag_for_review` decisions
