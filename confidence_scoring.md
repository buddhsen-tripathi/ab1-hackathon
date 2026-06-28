# Confidence Scoring

Confidence answers one question: **how much do we trust that the extraction got it right?**

It is not about whether required fields are present — that is handled separately by `missing_fields` and gates the routing decision. Confidence is about **source quality**: how reliable is the format the data came from?

---

## Why Source Matters

Clinical documentation lives in many formats. A structured weekly wound assessment has one input box per field — wound type, length, width, depth, drainage — filled out explicitly by the clinician. There is no ambiguity, no regex, no interpretation needed. A free-text nursing progress note might say *"wound to sacrum, looks better"* and require pattern matching to extract anything useful. These two sources should not be trusted equally.

The confidence score captures that difference systematically.

---

## The Formula

Every source type has two parameters:

```
confidence = base_confidence × (fields_found / 5)
```

- **`base_confidence`** — how trustworthy the format is structurally
- **`fields_found / 5`** — how much of the data was actually present

The denominator is always **5**, representing the five universal extraction targets:
`wound_type`, `length_cm`, `width_cm`, `depth_cm`, `drainage_amount`.

This is a fixed denominator regardless of wound type. Wound-type-aware required fields determine *routing* (a venous ulcer does not need depth to bill); they do not affect scoring. A venous note missing depth still gets `fields_found = 4` in the confidence formula.

---

## Source Types and Scores

| Source | Format Description | Base | Score |
|---|---|---|---|
| `assessment_structured` | Structured weekly wound sheet — explicit field-per-input | — | **0.98 (fixed)** |
| `assessment_narrative` | Long-text answer inside an assessment form | 0.85 | `0.85 × (n/5)`, floor 0.88 if complete |
| `note_soap` | Labeled SOAP/SPN note with `Location:`, `Length:` keys | — | **0.95** if ≥ 4 fields, else `0.75 × (n/5)` |
| `note_prose` | Envive narrative with `Meas.` or `measures aprx` | — | **0.90** if complete, else `0.75 × (n/5)` |
| `note_multi` | Multi-wound note — picks primary by completeness × size | 0.65 | `0.65 × (n/5)` |
| `note_text` | Generic free-text fallback | 0.60 | `0.60 × (n/5)`, floor 0.80 if complete |

### Worked Examples

**`assessment_structured`, all 5 fields present:**
```
confidence = 0.98  (hardcoded — machine-generated structured data)
```

**`assessment_narrative`, 4 of 5 fields found:**
```
confidence = 0.85 × (4/5) = 0.68
```

**`assessment_narrative`, all 5 fields found (complete):**
```
raw    = 0.85 × (5/5) = 0.85
floored to 0.88  (complete extraction from a narrative earns the floor)
confidence = 0.88
```

**`note_soap`, 4 fields found:**
```
confidence = 0.95  (≥ 4 fields threshold met)
```

**`note_soap`, 2 fields found:**
```
confidence = 0.75 × (2/5) = 0.30
```

**`note_prose`, wound type + length + width + drainage (4 fields):**
```
confidence = 0.75 × (4/5) = 0.60
```

**`note_text`, all 5 fields found (complete):**
```
raw    = 0.60 × (5/5) = 0.60
floored to 0.80  (complete extraction from free text earns the floor)
confidence = 0.80
```

**`note_text`, 2 fields found:**
```
confidence = 0.60 × (2/5) = 0.24  →  below reject threshold
```

---

## Floor Rules When Complete

When all 5 universal fields are present, each source has a minimum confidence it cannot fall below. Without floors, a `note_text` that found all 5 fields (`0.60 × 1.0 = 0.60`) would be flagged for review even though nothing is missing — which is over-conservative.

| Source | Floor (when complete) |
|---|---|
| `assessment_structured` | 0.98 (always) |
| `assessment_narrative` | 0.88 |
| `note_prose` | 0.90 |
| `note_text` | 0.80 |

`note_soap` and `note_multi` do not have explicit floors — their base formulas already produce reasonable values at full completeness.

---

## Fusion Bonus

When two sources are available (e.g. a structured assessment **and** a SOAP note), the pipeline merges them:

- **Primary** = the source with higher confidence
- **Secondary** fills any gaps the primary left

If the merged result is complete, confidence floors at **0.85** regardless of what the individual sources scored. Two independent sources producing the same data is stronger evidence than either alone.

```
merged = _merge(assessment_structured, note_soap)
if merged.is_complete():
    merged.confidence = max(merged.confidence, 0.85)
```

In practice, 92% of auto-accepted patients come from `assessment_structured + note_*` fusion, which yields **0.98** — the structured assessment dominates and the note fills any gaps.

---

## Routing Thresholds

Confidence and completeness together determine the routing decision:

```
Fields missing                 → flag_for_review  (regardless of confidence)
Confidence < 0.40              → reject           (data too noisy to act on)
Confidence 0.40 – 0.74        → flag_for_review  (present but uncertain)
Confidence ≥ 0.75 + complete   → auto_accept      ✓
```

**Why 0.75?**
It is the minimum a `note_soap` with 4+ fields can reach (0.95) and a `note_prose` with most fields can reach. Below 0.75, the extraction was working against a poorly structured note — a human should confirm before billing.

**Why 0.40 as the reject floor?**
Below 0.40, the extraction found fewer than 4 fields from a `note_text` or fewer than 4 from a `note_multi`. At that point, there is not enough reliable data to even tell a biller what to fix. A structured wound assessment should be obtained from scratch.

---

## In Practice

| Confidence Range | Count (MCB patients) | Typical Source |
|---|---|---|
| 0.98 | 83 patients | `assessment_structured + note_*` |
| 0.85 – 0.95 | 9 patients | `assessment_narrative + note_*` |
| 0.51 – 0.74 | 49 patients | Partial extractions — all flagged |
| < 0.40 | 0 patients | Would be rejected |

All 92 auto-accepted patients have confidence **≥ 0.85**. The 49 flagged patients have confidence between 0.51 and 0.98 — the ones at 0.98 are flagged for missing fields, not low confidence.
