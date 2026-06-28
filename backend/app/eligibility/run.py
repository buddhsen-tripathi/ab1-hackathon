"""Orchestrate routing: load patients + coverage + wound_extractions, reconcile
+ route each patient, write the patient_eligibility table, print a summary.

Run: python -m app.eligibility.run   (requires app.preprocess.run to have run)
"""
import json
import time
from collections import defaultdict

from ..db import connect
from . import routing, store
from .diagnoses import is_wound_code


def _load(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, patient_id, facility_id, raw FROM patients")
        patients = cur.fetchall()

        cur.execute("SELECT patient_id, payer_code, payer_type, effective_to FROM coverage")
        coverage = defaultdict(list)
        for r in cur.fetchall():
            coverage[r["patient_id"]].append(dict(r))

        cur.execute("SELECT * FROM wound_extractions WHERE is_primary = true")
        primary = defaultdict(list)
        for r in cur.fetchall():
            primary[r["patient_id"]].append(dict(r))

        cur.execute(
            "SELECT patient_id, COUNT(*) n FROM wound_extractions "
            "WHERE NOT is_primary GROUP BY 1"
        )
        secondary = {r["patient_id"]: r["n"] for r in cur.fetchall()}

        # patient_ids with an ACTIVE wound ICD-10 diagnosis (the Gate-2 set)
        cur.execute(
            "SELECT patient_id, icd10_code FROM diagnoses WHERE clinical_status='active'"
        )
        wound_dx = {r["patient_id"] for r in cur.fetchall() if is_wound_code(r["icd10_code"])}
    return patients, coverage, primary, secondary, wound_dx


def run_stream():
    """Generator form of the route stage: yields stage_start / progress /
    stage_complete events as patients are reconciled and routed."""
    conn = connect()
    try:
        store.init(conn)
        patients, coverage, primary, secondary, wound_dx = _load(conn)
        total = len(patients)
        yield {"type": "stage_start", "stage": "route", "total": total,
               "message": f"Reconciling and routing {total} patients"}

        results = []
        for i, p in enumerate(patients, 1):
            raw = p["raw"] or {}
            meta = {
                "internal_id": p["id"],
                "patient_id": p["patient_id"],
                "facility_id": p["facility_id"],
                "first_name": raw.get("first_name"),
                "last_name": raw.get("last_name"),
                "is_new_admission": raw.get("is_new_admission"),
                "secondary_wound_count": secondary.get(p["id"], 0),
            }
            results.append(
                routing.route(meta, coverage.get(p["patient_id"], []),
                              primary.get(p["id"], []),
                              p["patient_id"] in wound_dx)
            )
            if i % 50 == 0 or i == total:
                yield {"type": "progress", "stage": "route", "done": i, "total": total}

        store.replace_all([r.as_row() for r in results], conn)
        conn.commit()
        summary = store.summary(conn)
    finally:
        conn.close()

    yield {"type": "stage_complete", "stage": "route", "summary": summary}


def run():
    """Run the route stage to completion, printing a trace."""
    last = None
    for ev in run_stream():
        last = ev
    if last:
        print("=== ROUTING COMPLETE ===")
        print(json.dumps(last.get("summary", {}), indent=2))
    return last


def _route_all(patients, coverage, primary, secondary):
    results = []
    for p in patients:
        raw = p["raw"] or {}
        meta = {
            "internal_id": p["id"],
            "patient_id": p["patient_id"],
            "facility_id": p["facility_id"],
            "first_name": raw.get("first_name"),
            "last_name": raw.get("last_name"),
            "is_new_admission": raw.get("is_new_admission"),
            "secondary_wound_count": secondary.get(p["id"], 0),
        }
        results.append(
            routing.route(meta, coverage.get(p["patient_id"], []), primary.get(p["id"], []))
        )
    return results


if __name__ == "__main__":
    run()
