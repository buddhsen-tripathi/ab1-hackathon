# Data Quality Investigation

Why extraction and routing aren't "perfect" — findings from our 300-patient run.

---

## Summary

The data **is intentionally messy**, like real EHR exports. Imperfect results are mostly expected, not pipeline bugs.

| Issue | Count (of 300) | Root cause |
|---|---|---|
| Not Medicare Part B | 155 | Wrong payer — correctly rejected |
| MCB but incomplete wound docs | 85 | Missing fields in source notes |
| MCB but unparseable | 30 | Notes too sparse or contradictory |
| MCB + complete docs | 30 | Correctly auto-accepted |

---

## Finding 1: ~52% of patients aren't on Medicare Part B

155 patients have Medicaid, Medicare Part A, or HMO — **not billable under Part B wound care**. Our pipeline correctly rejects all of them.

This is not a data quality failure — it's the payer mix in the synthetic dataset (~60% MCB, ~40% other).

---

## Finding 2: Missing fields come from the source notes, not our schema

Among **145 MCB-eligible** patients, missing extracted fields:

| Field | Missing count | Why |
|---|---|---|
| `depth_cm` | 60 | Envive notes often give L×W only: `Measures 2.9 cm x 2.8 cm` — no depth |
| `drainage_amount` | 59 | Shorthand (`Mod serosang`) or omitted entirely |
| `wound_type` | 49 | Multi-wound notes describe location without type keyword |
| `length_cm` / `width_cm` | 13 each | Sparse or vague notes |

**Example — Envive format (depth missing by design in note):**
```
Wound Status: Pressure Ulcer to Right hip / Measures 2.9 cm x 2.8 cm / Stage: Stage 3
Drainage present - serosanguineous, heavy.
```
→ We get type, stage, L, W, drainage — but **no depth in source text**.

---

## Finding 3: Note format drives completeness

| Format | MCB patients | Fully complete | Missing depth | Missing wound type |
|---|---|---|---|---|
| **Envive** | 44 | 11 (25%) | 33 (75%) | 0 |
| **Multi-wound** | 64 | 17 (27%) | 4 | 28 (44%) |
| **Prose** | 37 | 2 (5%) | 23 | 21 (57%) |

- **Envive**: structured-ish but rarely includes depth
- **Multi-wound**: two wounds in one note — primary-wound selection often grabs a segment with dimensions but no type keyword (`L heel 3.5x2.7`)
- **Prose**: heavy shorthand — hardest for regex

---

## Finding 4: Flag-for-review breakdown (MCB patients)

| Missing field combo | Count |
|---|---|
| depth only | 44 |
| drainage only | 16 |
| wound_type + drainage | 13 |
| wound_type only | 9 |

These are **correct flags** — the biller should chase missing documentation, not submit incomplete claims.

---

## Finding 5: 42 patients have dimensions but no wound type

Example: `FA-009` — extracted `5.3 × 4.5 × 0.8 cm, moderate drainage` but note never says "pressure ulcer" explicitly in the selected segment.

Fix path: improve multi-wound parser + LLM fallback for type inference.

---

## What "good enough" looks like

For a **triage** pipeline (not claim submission):

| Outcome | Our count | Purpose |
|---|---|---|
| Auto-accept | 30 | Biller can proceed without opening chart |
| Flag for review | 85 | Biller knows exactly what's missing |
| Reject (wrong payer) | 155 | Don't waste time |
| Reject (MCB, no data) | 30 | Need structured assessment first |

**False auto-accept is the worst error** — we keep that number conservative (30/300 = 10%).

---

## Planned improvements

1. **LLM verification** — second pass on auto-accept cases only (~30 patients, ~$0.02/run)
2. **Better multi-wound type extraction** — regex for `Pressure Ulcer Left buttock`
3. **Separate payer eligibility from documentation routing** — clearer UI badges
4. **Depth inference** — do NOT guess; flag for review is correct when source lacks depth

---

## Related docs

- [PROBLEM.md](./PROBLEM.md) — what problem we're solving
- [PROJECT.md](./PROJECT.md) — architecture
