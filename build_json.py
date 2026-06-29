"""
Regenerates dashboard/public/eligibility_data.json from the latest
eligibility_output.csv plus the raw data CSVs.

Run after eligibility.py to push fresh routing decisions to the dashboard.
"""
import ast
import json
import math

import pandas as pd

elig        = pd.read_csv("data/eligibility_output.csv")
notes_df    = pd.read_csv("data/notes.csv")
assess_df   = pd.read_csv("data/assessments.csv")
diagnoses_df = pd.read_csv("data/diagnoses.csv")
coverage_df = pd.read_csv("data/coverage.csv")


def _clean(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def notes_for(pid: str):
    rows = notes_df[notes_df["patient_id_str"] == pid].sort_values(
        "effective_date", ascending=False
    )
    return [
        {
            "note_type":      _clean(r.get("note_type")),
            "effective_date": _clean(r.get("effective_date")),
            "note_text":      _clean(r.get("note_text")),
            "created_by":     _clean(r.get("created_by")),
        }
        for _, r in rows.iterrows()
    ]


def assessment_for(pid: str):
    rows = assess_df[assess_df["patient_id_str"] == pid].sort_values(
        "assessment_date", ascending=False
    )
    if rows.empty:
        return None
    r = rows.iloc[0]
    sections = None
    raw = r.get("raw_sections")
    if raw and not (isinstance(raw, float) and math.isnan(raw)):
        try:
            sections = ast.literal_eval(str(raw))
        except Exception:
            pass
    return {
        "assessment_type": _clean(r.get("assessment_type")),
        "assessment_date": _clean(r.get("assessment_date") or r.get("raw_assessmentDate")),
        "status":          _clean(r.get("status") or r.get("raw_status")),
        "sections":        sections,
    }


def diagnoses_for(pid: str):
    rows = diagnoses_df[diagnoses_df["patient_id"] == pid]
    return [
        {
            "icd10_code":        _clean(r.get("icd10_code")),
            "icd10_description": _clean(r.get("icd10_description")),
            "clinical_status":   _clean(r.get("clinical_status")),
            "onset_date":        _clean(r.get("onset_date")),
        }
        for _, r in rows.iterrows()
    ]


def coverage_for(pid: str):
    rows = coverage_df[coverage_df["patient_id"] == pid]
    if rows.empty:
        return None
    r = rows.iloc[0]
    eff_to = r.get("effective_to")
    return {
        "payer_name":     _clean(r.get("payer_name")),
        "payer_code":     _clean(r.get("payer_code")),
        "payer_type":     _clean(r.get("payer_type")),
        "effective_from": _clean(r.get("effective_from")),
        "effective_to":   None if (isinstance(eff_to, float) and math.isnan(eff_to)) or str(eff_to).strip() == "" else _clean(eff_to),
    }


records = []
for _, row in elig.iterrows():
    pid = row["patient_id"]
    rec = {k: _clean(v) for k, v in row.to_dict().items()}
    rec["notes"]      = notes_for(pid)
    rec["assessment"] = assessment_for(pid)
    rec["diagnoses"]  = diagnoses_for(pid)
    rec["coverage"]   = coverage_for(pid)
    records.append(rec)

out = "dashboard/public/eligibility_data.json"
with open(out, "w") as f:
    json.dump(records, f, default=str)

print(f"Wrote {len(records)} patients → {out}")
