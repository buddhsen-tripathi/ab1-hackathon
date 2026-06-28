# What Problem Are We Solving?

A plain-language guide for anyone who isn't from healthcare.

---

## The setting (30 seconds)

Imagine a **nursing home or rehab facility** with hundreds of elderly patients. Many have **wounds** — bedsores (pressure ulcers), diabetic foot sores, leg ulcers, etc. Nurses and doctors treat these wounds daily and write notes about them in an electronic health record (EHR) called **PointClickCare (PCC)**.

The facility wants to **get paid** by insurance for specialized wound care services. But insurance won't pay unless very specific documentation exists. Someone on the **billing team** has to figure out, patient by patient: *"Can we submit a claim for this person today?"*

That's the job we're automating.

---

## Why is billing hard here?

### 1. Not every patient qualifies

Wound care under **Medicare Part B** (outpatient insurance for seniors) only applies when **all three** are true:

| Requirement | What it means |
|---|---|
| Active wound | Patient currently has a documented wound (pressure ulcer, diabetic ulcer, etc.) |
| Right insurance | Patient has **active Medicare Part B** coverage — not Part A, Medicaid, or HMO |
| Complete documentation | Wound size is recorded as **length, width, depth** (in cm) **and** drainage level (none / light / moderate / heavy) |

If any piece is missing, the claim gets **denied** — the facility does the work but doesn't get paid.

### 2. The data is messy

Clinical info lives in **free-text nurse notes**, not neat spreadsheets:

```
Wound note - Rightbuttock. Meas 9.2x4.6x2.7cm. Heavy serosang drainage...
```

Or narrative paragraphs where measurements are buried in prose. Sometimes a note describes **two wounds** and the biller must figure out which one matters.

A human biller opens PCC, reads notes one by one, checks insurance, and mentally extracts: wound type, size, drainage. For **300 patients across 3 facilities**, that's hours of repetitive reading.

### 3. Wrong payer = wasted effort

~40% of patients in the dataset **don't have Medicare Part B**. A biller who tries to process them is wasting time — they'll never be billable under this workflow.

### 4. The API is unreliable (in real life too)

PCC throttles integrations. Our mock API returns **HTTP 429 (rate limit)** on 30% of requests. A pipeline that doesn't retry will fail mid-run.

---

## What is the biller's actual job?

Think of them as a **triage clerk**, not a doctor:

1. Look at today's patient list
2. Find who **might** be billable for wound care under Medicare Part B
3. Check documentation is **complete enough** to submit a claim
4. Route each patient:
   - **Ready to bill** → send to claims team
   - **Needs review** → ask a nurse/clinician to fill in missing info
   - **Don't bother** → wrong insurance or no usable wound data

They are **not** diagnosing patients or choosing treatments. They are checking paperwork readiness.

---

## What does the hackathon ask us to build?

From the official challenge, the required deliverables are:

1. **Pipeline** — Pull all patient data from the mock PCC API (handle rate limits)
2. **Extraction** — Pull wound type, stage, location, measurements, drainage from notes + assessments
3. **Eligibility table** — One row per patient with insurance status + routing decision + reason
4. **Presentation** — Show results so a non-technical biller understands what to act on
5. **Visual output** — Dashboard or UI, not just a raw CSV

The routing decisions are fixed:

| Decision | Meaning |
|---|---|
| `auto_accept` | Documentation looks complete — safe to route to billing |
| `flag_for_review` | Something is missing or ambiguous — human should check |
| `reject` | Wrong insurance or can't extract reliable wound data |

---

## What is BillReady's solution?

BillReady is a **billing triage desk**, not a full billing system.

```
PCC API  →  fetch & cache patient data
         →  extract wound details from messy notes
         →  check Medicare Part B eligibility
         →  route each patient with a plain-English reason
         →  show biller a prioritized worklist
```

**In one sentence:** We replace the biller's manual chart-reading with an automated first pass that tells them *who to look at first and why*.

---

## Does our project actually solve the given problem?

### Yes — for what the hackathon defines

| Hackathon requirement | BillReady |
|---|---|
| Data ingestion with rate-limit handling | ✅ Async pipeline, retry on 429, SQLite cache |
| Wound field extraction from notes + assessments | ✅ Tiered parsers (assessment JSON, prose, Envive, multi-wound) |
| Eligibility output with routing + reasons | ✅ CSV + SQLite with plain-English explanations |
| Biller-friendly presentation | ✅ Streamlit worklist with swimlanes |
| Visual dashboard | ✅ Triage desk with filters and patient detail |

We are solving the **exact problem stated in the README**: automate data collection and triage for Medicare Part B wound care billing.

### No — and we shouldn't pretend otherwise

BillReady does **not**:

- Submit claims to Medicare
- Guarantee 100% extraction accuracy (notes are ambiguous by design)
- Replace clinical judgment on which wound to treat
- Handle billing codes (CPT/ICD), prior auth, or payment reconciliation
- Work with real PCC in production (this is a mock API)

That's fine. The hackathon problem is specifically the **triage step** — not the full revenue cycle.

### Honest assessment of our routing numbers

From our last run (300 patients):

| Status | Count | What it means |
|---|---|---|
| Ready to bill | ~30 | MCB + all 5 wound fields extracted with confidence |
| Needs review | ~85 | MCB patient but missing depth, ambiguous note, or low confidence |
| Rejected | ~185 | Mostly wrong insurance (~155 non-MCB) + some unparseable notes |

This is realistic: most patients aren't Medicare Part B wound care candidates. The value is surfacing the **~30 ready** and **~85 that need a quick look** instead of making a biller open all 300 charts.

---

## Who benefits and how?

| Person | Before BillReady | After BillReady |
|---|---|---|
| **Biller** | Opens 300 charts manually | Opens worklist, starts with 30 "ready to bill" |
| **Wound nurse** | Gets vague "check this patient" requests | Gets specific "missing depth measurement" flags |
| **Facility admin** | Revenue delayed by manual bottleneck | Faster identification of billable encounters |

---

## Analogy (if healthcare still feels abstract)

Think of an **immigration document checker** at an airport:

- Travelers (patients) arrive with passports, visas, forms (clinical notes, insurance)
- The checker (biller) must verify: right visa type? all fields filled? photo match?
- Most travelers are rejected quickly (wrong visa type = wrong insurance)
- Some need secondary inspection (flag for review = missing field)
- A few pass straight through (auto accept = complete documentation)

BillReady is the **automated pre-screening line** — not the immigration officer, not the airline, not the embassy.

---

## What should we stay focused on?

For the hackathon presentation, anchor everything to the **given problem**:

1. **Show the pain** — "A biller manually reads wound notes in PCC for every patient"
2. **Show the pipeline** — fetch → extract → route → display
3. **Demo 3 patients** — one auto-accept, one flag-for-review, one reject — and explain why
4. **Be honest about limits** — extraction isn't perfect; we flag ambiguity instead of guessing

Don't drift into generic "AI healthcare platform" talk. The judges care about **methodology, extraction accuracy, routing logic, and presentation** — all tied to this specific billing triage workflow.

---

## Related docs

- [README.md](./README.md) — official hackathon challenge
- [PROJECT.md](./PROJECT.md) — our architecture and differentiation
- [API.md](./API.md) — mock PCC API reference
