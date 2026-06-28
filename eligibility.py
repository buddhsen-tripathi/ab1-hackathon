"""
Medicare Part B wound care billing triage.

Gate 1 — Payer: patient must have active MCB coverage (payer_code == MCB and
          coverage effective_to is null or in the future).
Gate 2 — ICD-10: patient must have an active wound diagnosis.
          If wound IS documented in notes but ICD-10 is missing → flag_for_review.
          If neither wound docs nor ICD-10 → reject.
Gate 3 — Extraction completeness + confidence:
          Missing required fields (wound-type-aware) → flag_for_review.
          Confidence < 0.40 → reject (data unreliable).
          Confidence 0.40–0.74 → flag_for_review (clinician verify).
          Confidence >= 0.75 + complete → auto_accept.

Routing decisions: auto_accept | flag_for_review | reject
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from extraction import extract_patient_wound
from models import RoutingDecision, WoundExtraction

# ICD-10 prefixes that indicate a billable wound condition
WOUND_ICD_PREFIXES = (
    "L89",   # pressure ulcer
    "E11.62", # type 2 diabetic foot ulcer
    "E10.62", # type 1 diabetic foot ulcer
    "I83",   # venous ulcer
    "I70.2", # arterial ulcer
    "L02",   # abscess / cellulitis
    "L97",   # non-pressure ulcer of lower limb
    "L98",   # other chronic skin ulcer
    "T20", "T21", "T22", "T23", "T24", "T25",  # burns
)

CONFIDENCE_ACCEPT = 0.75
CONFIDENCE_REJECT = 0.40

_FIELD_LABELS = {
    "wound_type":      "Wound type",
    "stage":           "Stage",
    "length_cm":       "Length",
    "width_cm":        "Width",
    "depth_cm":        "Depth",
    "drainage_amount": "Drainage",
}


def has_active_wound_dx(patient_id: str, diagnoses_df: pd.DataFrame) -> bool:
    dx = diagnoses_df[
        (diagnoses_df["patient_id"] == patient_id)
        & (diagnoses_df["clinical_status"] == "active")
    ]
    return dx["icd10_code"].apply(
        lambda c: any(str(c).startswith(p) for p in WOUND_ICD_PREFIXES)
    ).any()


def _has_active_mcb(patient_id: str, coverage_df: pd.DataFrame) -> bool:
    now = datetime.now(timezone.utc)
    records = coverage_df[coverage_df["patient_id"] == patient_id]
    for _, rec in records.iterrows():
        if str(rec.get("payer_code", "")).upper() != "MCB":
            continue
        eff_to = rec.get("effective_to")
        if eff_to is None or (isinstance(eff_to, float) and pd.isna(eff_to)) or str(eff_to).strip() == "":
            return True
        try:
            end = datetime.fromisoformat(str(eff_to).replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if end >= now:
                return True
        except ValueError:
            continue
    return False


def route(
    patient: dict,
    wound: WoundExtraction | None,
    has_wound_dx: bool,
) -> tuple[RoutingDecision, str]:
    payer = patient.get("primary_payer_code", "")
    mcb_coverage_active = patient.get("_mcb_coverage_active", payer == "MCB")

    # ── Gate 1: Payer ─────────────────────────────────────────────────────────
    if payer != "MCB" or not mcb_coverage_active:
        return "reject", f"Not eligible for Medicare Part B wound care billing — payer: {payer}"

    # ── Gate 2: Active wound ICD-10 ───────────────────────────────────────────
    if not has_wound_dx:
        if wound and wound.wound_type:
            return (
                "flag_for_review",
                "Wound documented in notes but no supporting ICD-10 diagnosis on record — "
                "claim will be denied without diagnosis code. "
                "Clinician must add wound diagnosis before billing.",
            )
        return "reject", "MCB patient with no wound diagnosis and no wound documentation."

    # ── Gate 3: Extraction completeness + confidence ──────────────────────────
    if wound is None:
        return (
            "flag_for_review",
            "Active Medicare Part B and wound diagnosis present, but no wound measurements "
            "found in notes or assessments.",
        )

    missing = wound.missing_fields()
    if missing:
        missing_str = ", ".join(_FIELD_LABELS.get(f, f) for f in missing)
        return (
            "flag_for_review",
            f"Missing required field(s): {missing_str}. "
            "Review chart and obtain missing data before billing.",
        )

    if wound.confidence < CONFIDENCE_REJECT:
        return (
            "reject",
            f"Active Medicare Part B and wound diagnosis present but wound data could not be "
            f"reliably extracted (confidence {wound.confidence:.0%}). "
            "Obtain a structured wound assessment.",
        )

    if wound.confidence < CONFIDENCE_ACCEPT:
        return (
            "flag_for_review",
            f"All required wound fields documented but extraction confidence is low "
            f"({wound.confidence:.0%}). "
            f"Clinician should verify measurements before billing. Source: {wound.source}.",
        )

    return "auto_accept", _build_accept_reason(wound)


def _build_accept_reason(wound: WoundExtraction) -> str:
    parts = ["MCB coverage active; active wound diagnosis"]
    if wound.wound_type:
        wt = wound.wound_type
        if wound.stage:
            wt += f" {wound.stage}"
        parts.append(wt)
    dims = []
    if wound.length_cm is not None:
        dims.append(f"L {wound.length_cm:.1f}")
    if wound.width_cm is not None:
        dims.append(f"W {wound.width_cm:.1f}")
    if wound.depth_cm is not None:
        dims.append(f"D {wound.depth_cm:.1f}")
    if dims:
        parts.append(" × ".join(dims) + " cm")
    if wound.drainage_amount:
        parts.append(f"{wound.drainage_amount} drainage")
    parts.append(f"source: {wound.source} ({wound.confidence:.0%})")
    return "; ".join(parts)


def build_eligibility_table() -> pd.DataFrame:
    patients    = pd.read_csv("data/patients.csv")
    diagnoses   = pd.read_csv("data/diagnoses.csv")
    coverage    = pd.read_csv("data/coverage.csv")
    assessments = pd.read_csv("data/assessments.csv")
    notes       = pd.read_csv("data/notes.csv")

    records = []
    for _, pat in patients.iterrows():
        pid   = pat["patient_id"]
        payer = pat.get("primary_payer_code", "")

        mcb_active = _has_active_mcb(pid, coverage) if payer == "MCB" else False

        pat_ass   = assessments[assessments["patient_id_str"] == pid]
        pat_notes = notes[notes["patient_id_str"] == pid]
        wound = extract_patient_wound(pat_ass, pat_notes) if payer == "MCB" else None

        has_dx = has_active_wound_dx(pid, diagnoses)

        pat_dict = pat.to_dict()
        pat_dict["_mcb_coverage_active"] = mcb_active

        decision, reason = route(pat_dict, wound, has_dx)

        records.append({
            "patient_id":          pid,
            "facility_id":         pat["facility_id"],
            "first_name":          pat["first_name"],
            "last_name":           pat["last_name"],
            "payer_code":          payer,
            "mcb_coverage_active": mcb_active,
            "active_wound_dx":     has_dx,
            "wound_type":          wound.wound_type if wound else None,
            "stage":               wound.stage if wound else None,
            "location":            wound.location if wound else None,
            "length_cm":           wound.length_cm if wound else None,
            "width_cm":            wound.width_cm if wound else None,
            "depth_cm":            wound.depth_cm if wound else None,
            "drainage":            wound.drainage_amount if wound else None,
            "data_source":         wound.source if wound else None,
            "confidence":          wound.confidence if wound else None,
            "missing_fields":      "|".join(wound.missing_fields()) if wound else None,
            "routing":             decision,
            "reason":              reason,
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
    sample_aa = df[df["routing"] == "auto_accept"].head(3)
    if len(sample_aa):
        print(sample_aa[
            ["patient_id", "wound_type", "location", "length_cm", "width_cm",
             "depth_cm", "drainage", "confidence", "reason"]
        ].to_string(index=False))

    print()
    print("=== Sample flag_for_review ===")
    sample_flag = df[df["routing"] == "flag_for_review"].head(3)
    if len(sample_flag):
        print(sample_flag[
            ["patient_id", "wound_type", "length_cm", "drainage", "missing_fields", "reason"]
        ].to_string(index=False))

    print()
    print("=== Sample reject ===")
    sample_rej = df[df["routing"] == "reject"].head(3)
    if len(sample_rej):
        print(sample_rej[["patient_id", "payer_code", "reason"]].to_string(index=False))

    df.to_csv("data/eligibility_output.csv", index=False)
    print(f"\nSaved {len(df)} rows → data/eligibility_output.csv")
