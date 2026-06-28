"""Characterize the ingested data so we know exactly what we're parsing.

Classifies:
  - note format families (SOAP vs Envive narrative)
  - assessment raw_json shapes (structured Q/A vs narrative blob)
  - measurement dimensionality (L x W x D vs L x W only -> depth missing)
  - payer / coverage signal (MCB active vs ambiguous "Medicare")
  - dirty-data traps (doubled words, laterality conflicts, multi-wound)
"""
import json
import re
from collections import Counter

from . import db

# 2 or 3 dimensions: "2.9 cm x 2.8 cm", "2.8 cm x 3.8 cm x 1.4 cm", "4.2x3.1x1.5"
MEAS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:cm)?\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:cm)?"
    r"(?:\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:cm)?)?",
    re.IGNORECASE,
)
DOUBLED_WORD_RE = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)
DRAINAGE_RE = re.compile(
    r"\b(none|scant|minimal|small|light|moderate|large|heavy|copious)\b",
    re.IGNORECASE,
)
LATERALITY_RE = re.compile(r"\b(left|right|bilateral)\b", re.IGNORECASE)


def classify_note_format(text):
    if not text:
        return "empty"
    low = text.lower()
    if "envive" in low or re.search(r"measures\b.*\bstage:", low):
        return "envive_narrative"
    if "subjective:" in low and "objective:" in low:
        return "soap"
    if re.search(r"location:|wound type:|length:", low):
        return "structured_spn"
    return "other"


def measurement_dims(text):
    """Return 3, 2, or 0 — how many dimensions were stated."""
    m = MEAS_RE.search(text or "")
    if not m:
        return 0
    return 3 if m.group(3) else 2


def classify_assessment(raw_json):
    """Return (shape, has_narrative_blob, section_names)."""
    if not raw_json:
        return "empty", False, []
    try:
        j = json.loads(raw_json)
    except Exception:
        return "unparseable", False, []
    sections = j.get("sections", [])
    names = [s.get("sectionName") for s in sections]
    has_narrative = False
    for s in sections:
        for q in s.get("questions", []):
            qn = (q.get("question") or "").lower()
            if "narrative" in qn and isinstance(q.get("answer"), str):
                has_narrative = True
    if has_narrative:
        return "narrative_blob", True, names
    return "structured_qa", False, names


def report():
    conn = db.connect()
    rep = {"table_counts": db.counts(conn)}

    # ---- patients / payer mix ----
    payer_mix = Counter()
    by_facility = Counter()
    for r in conn.execute(
        "SELECT facility_id, primary_payer_code FROM patients"
    ):
        payer_mix[r["primary_payer_code"]] += 1
        by_facility[r["facility_id"]] += 1
    total_patients = sum(payer_mix.values())
    rep["patients"] = {
        "total": total_patients,
        "by_facility": dict(by_facility),
        "primary_payer_mix": dict(payer_mix),
        "billable_MCB": payer_mix.get("MCB", 0),
        "billable_MCB_pct": round(100 * payer_mix.get("MCB", 0) / max(total_patients, 1), 1),
    }

    # ---- coverage signal ----
    cov_code = Counter()
    cov_type = Counter()
    active_mcb_patients = set()
    for r in conn.execute(
        "SELECT patient_id, payer_code, payer_type, effective_to FROM coverage"
    ):
        cov_code[r["payer_code"]] += 1
        cov_type[r["payer_type"]] += 1
        if r["payer_code"] == "MCB" and not r["effective_to"]:
            active_mcb_patients.add(r["patient_id"])
    rep["coverage"] = {
        "payer_code_distribution": dict(cov_code),
        "payer_type_distribution": dict(cov_type),
        "patients_with_active_MCB": len(active_mcb_patients),
        "note": "payer_type often just says 'Medicare' (A vs B ambiguous) -> "
        "must use payer_code MCB to confirm Part B",
    }

    # ---- diagnoses ----
    diag_status = Counter()
    for r in conn.execute("SELECT clinical_status FROM diagnoses"):
        diag_status[r["clinical_status"]] += 1
    rep["diagnoses"] = {"clinical_status": dict(diag_status)}

    # ---- notes ----
    note_type = Counter()
    note_format = Counter()
    note_dims = Counter()
    note_drainage_found = 0
    note_doubled_word = 0
    note_total = 0
    note_format_by_type = {}
    sample_by_format = {}
    for r in conn.execute("SELECT note_type, note_text FROM notes"):
        note_total += 1
        nt = r["note_type"]
        txt = r["note_text"] or ""
        fmt = classify_note_format(txt)
        note_type[nt] += 1
        note_format[fmt] += 1
        note_format_by_type.setdefault(nt, Counter())[fmt] += 1
        note_dims[measurement_dims(txt)] += 1
        if DRAINAGE_RE.search(txt):
            note_drainage_found += 1
        if DOUBLED_WORD_RE.search(txt):
            note_doubled_word += 1
        if fmt not in sample_by_format:
            sample_by_format[fmt] = txt[:300]
    rep["notes"] = {
        "total": note_total,
        "note_type_distribution": dict(note_type),
        "format_family": dict(note_format),
        "format_by_note_type": {k: dict(v) for k, v in note_format_by_type.items()},
        "measurement_dims": {
            "three_LxWxD": note_dims.get(3, 0),
            "two_LxW_no_depth": note_dims.get(2, 0),
            "none_found": note_dims.get(0, 0),
        },
        "drainage_keyword_found": note_drainage_found,
        "doubled_word_trap": note_doubled_word,
        "samples_by_format": sample_by_format,
    }

    # ---- assessments ----
    assess_type = Counter()
    assess_shape = Counter()
    assess_section_names = Counter()
    assess_dims = Counter()
    laterality_conflict = 0
    assess_total = 0
    sample_assess = {}
    for r in conn.execute(
        "SELECT assessment_type, status, raw_json FROM assessments"
    ):
        assess_total += 1
        assess_type[r["assessment_type"]] += 1
        shape, has_narr, names = classify_assessment(r["raw_json"])
        assess_shape[shape] += 1
        for n in names:
            assess_section_names[n] += 1
        raw = r["raw_json"] or ""
        assess_dims[measurement_dims(raw)] += 1
        if shape not in sample_assess:
            sample_assess[shape] = raw[:400]
        # laterality conflict: a 'Location' side that disagrees with 'Laterality'
        try:
            j = json.loads(r["raw_json"])
            loc_side = lat_side = None
            for s in j.get("sections", []):
                for q in s.get("questions", []):
                    qn = (q.get("question") or "").lower()
                    ans = q.get("answer")
                    if not isinstance(ans, str):
                        continue
                    m = LATERALITY_RE.search(ans)
                    if "location" in qn and m:
                        loc_side = m.group(1).lower()
                    if "laterality" in qn and m:
                        lat_side = m.group(1).lower()
            if loc_side and lat_side and loc_side != lat_side and "bilateral" not in (loc_side,):
                if loc_side != lat_side:
                    laterality_conflict += 1
        except Exception:
            pass
    rep["assessments"] = {
        "total": assess_total,
        "assessment_type_distribution": dict(assess_type),
        "raw_json_shape": dict(assess_shape),
        "section_names": dict(assess_section_names),
        "measurement_dims": {
            "three_LxWxD": assess_dims.get(3, 0),
            "two_LxW_no_depth": assess_dims.get(2, 0),
            "none_found": assess_dims.get(0, 0),
        },
        "laterality_conflict_trap": laterality_conflict,
        "samples_by_shape": sample_assess,
    }

    conn.close()
    return rep


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
