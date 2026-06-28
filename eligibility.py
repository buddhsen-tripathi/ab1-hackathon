"""
Eligibility logic — merges patients, coverage, diagnoses, and extracted wound
fields into one row per patient with a routing decision and plain-English reason.

Routing decisions:
  auto_accept     — MCB + active wound dx + complete measurements + drainage
  flag_for_review — MCB + partial data or ambiguous extraction
  reject          — not MCB, or extraction failed entirely
"""

import pandas as pd
from extraction import extract_all

WOUND_ICD_PREFIXES = (
    "L89", "E11.62", "I83", "I70.2", "L02", "L97", "L98",
    "T20", "T21", "T22", "T23", "T24", "T25",
)

REQUIRED_MEASUREMENT_FIELDS = ["length_cm", "width_cm"]  # depth missing in Envive — not hard-required
REQUIRED_FIELDS = ["wound_type", "drainage"] + REQUIRED_MEASUREMENT_FIELDS


def has_active_wound_dx(patient_id, diagnoses_df):
    dx = diagnoses_df[
        (diagnoses_df["patient_id"] == patient_id) &
        (diagnoses_df["clinical_status"] == "active")
    ]
    return dx["icd10_code"].apply(
        lambda c: any(str(c).startswith(p) for p in WOUND_ICD_PREFIXES)
    ).any()


def route(patient, wound, has_wound_dx):
    payer = patient.get("primary_payer_code")
    pid   = patient.get("patient_id")

    # ── Step 1: payer check ───────────────────────────────────────────────────
    if payer != "MCB":
        return "reject", f"Not Medicare Part B (payer: {payer})"

    # ── Step 2: wound diagnosis check ─────────────────────────────────────────
    if not has_wound_dx:
        # Still might have wound data from notes — downgrade to flag
        if wound.get("wound_type"):
            return (
                "flag_for_review",
                "No wound ICD-10 diagnosis on record, but wound documented in notes — clinician review needed",
            )
        return "reject", "MCB patient with no wound diagnosis and no wound documentation"

    # ── Step 3: extraction completeness ───────────────────────────────────────
    missing = [f for f in REQUIRED_FIELDS if not wound.get(f)]
    partial = [f for f in ["depth_cm", "stage", "location"] if not wound.get(f)]

    if missing:
        return (
            "flag_for_review",
            f"Missing required field(s): {', '.join(missing)}",
        )

    # ── Step 4: all clear ─────────────────────────────────────────────────────
    depth_note = " (depth not documented — Envive note format)" if not wound.get("depth_cm") else ""
    stage_note = "" if wound.get("stage") else "; stage not documented (non-pressure wound)"
    return (
        "auto_accept",
        f"MCB coverage active; active wound diagnosis; measurements and drainage documented{depth_note}{stage_note}",
    )


def build_eligibility_table():
    patients    = pd.read_csv("data/patients.csv")
    diagnoses   = pd.read_csv("data/diagnoses.csv")
    coverage    = pd.read_csv("data/coverage.csv")
    assessments = pd.read_csv("data/assessments.csv")
    notes       = pd.read_csv("data/notes.csv")

    wound_df = extract_all(assessments, notes)
    wound_map = wound_df.set_index("patient_id").to_dict("index")

    records = []
    for _, pat in patients.iterrows():
        pid   = pat["patient_id"]
        wound = wound_map.get(pid, {})

        has_dx = has_active_wound_dx(pid, diagnoses)
        decision, reason = route(pat.to_dict(), wound, has_dx)

        records.append({
            "patient_id":      pid,
            "facility_id":     pat["facility_id"],
            "first_name":      pat["first_name"],
            "last_name":       pat["last_name"],
            "payer_code":      pat["primary_payer_code"],
            "active_wound_dx": has_dx,
            "wound_type":      wound.get("wound_type"),
            "stage":           wound.get("stage"),
            "location":        wound.get("location"),
            "length_cm":       wound.get("length_cm"),
            "width_cm":        wound.get("width_cm"),
            "depth_cm":        wound.get("depth_cm"),
            "drainage":        wound.get("drainage"),
            "data_source":     wound.get("data_source"),
            "routing":         decision,
            "reason":          reason,
        })

    return pd.DataFrame(records)


if __name__ == "__main__":
    df = build_eligibility_table()

    print("=== Routing decisions ===")
    print(df["routing"].value_counts().to_string())

    print()
    print("=== MCB patients only ===")
    mcb = df[df["payer_code"] == "MCB"]
    print(mcb["routing"].value_counts().to_string())

    print()
    print("=== Sample auto_accept ===")
    print(df[df["routing"] == "auto_accept"].head(3)[
        ["patient_id", "wound_type", "location", "length_cm", "width_cm", "depth_cm", "drainage", "reason"]
    ].to_string(index=False))

    print()
    print("=== Sample flag_for_review ===")
    print(df[df["routing"] == "flag_for_review"].head(3)[
        ["patient_id", "wound_type", "length_cm", "drainage", "reason"]
    ].to_string(index=False))

    print()
    print("=== Sample reject ===")
    print(df[df["routing"] == "reject"].head(3)[
        ["patient_id", "payer_code", "reason"]
    ].to_string(index=False))

    df.to_csv("data/eligibility_output.csv", index=False)
    print(f"\nSaved {len(df)} rows → data/eligibility_output.csv")
