"""Persistence for the biller-facing output (`patient_eligibility` table)."""
from contextlib import contextmanager

from psycopg.types.json import Jsonb

from ..db import connect


@contextmanager
def _session(conn):
    """Reuse a caller-owned connection, or open a short-lived one. Reusing one
    connection per run avoids Neon's 2-6s per-connect cold-start tax."""
    if conn is not None:
        yield conn          # caller owns commit/close
    else:
        c = connect()
        try:
            yield c
            c.commit()
        finally:
            c.close()

DDL = """
CREATE TABLE IF NOT EXISTS patient_eligibility (
    internal_id BIGINT PRIMARY KEY,
    patient_id TEXT,
    facility_id INTEGER,
    first_name TEXT,
    last_name TEXT,
    is_new_admission BOOLEAN,
    has_active_mcb BOOLEAN,
    submission_eligible BOOLEAN,
    wound_type TEXT,
    stage TEXT,
    location TEXT,
    laterality TEXT,
    length_cm REAL,
    width_cm REAL,
    depth_cm REAL,
    area_cm2 REAL,
    drainage_amount TEXT,
    extraction_source TEXT,
    extraction_confidence REAL,
    routing_decision TEXT,
    reason TEXT,
    missing_fields JSONB,
    flags JSONB,
    secondary_wound_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_elig_decision ON patient_eligibility(routing_decision);
CREATE INDEX IF NOT EXISTS idx_elig_facility ON patient_eligibility(facility_id);
"""

_COLS = [
    "internal_id", "patient_id", "facility_id", "first_name", "last_name",
    "is_new_admission", "has_active_mcb", "submission_eligible", "wound_type",
    "stage", "location", "laterality", "length_cm", "width_cm", "depth_cm",
    "area_cm2", "drainage_amount", "extraction_source", "extraction_confidence",
    "routing_decision", "reason", "missing_fields", "flags", "secondary_wound_count",
]
_JSONB_COLS = {"missing_fields", "flags"}


def init(conn=None):
    with _session(conn) as c, c.cursor() as cur:
        cur.execute(DDL)


def replace_all(rows, conn=None):
    # Single multi-row INSERT per chunk = one network round-trip per chunk
    # (executemany round-trips per row, which is painfully slow over Neon).
    cols_sql = ",".join(_COLS)
    one = "(" + ",".join(["%s"] * len(_COLS)) + ")"
    chunk = max(1, 30000 // len(_COLS))
    with _session(conn) as c, c.cursor() as cur:
        cur.execute("TRUNCATE patient_eligibility")
        for i in range(0, len(rows), chunk):
            batch = rows[i:i + chunk]
            values_sql = ",".join([one] * len(batch))
            params = [
                Jsonb(r.get(c2)) if c2 in _JSONB_COLS else r.get(c2)
                for r in batch for c2 in _COLS
            ]
            cur.execute(
                f"INSERT INTO patient_eligibility ({cols_sql}) VALUES {values_sql}",
                params,
            )


def fetch_results(decision=None, facility_id=None, search=None,
                  eligible=None, new_admission=None, missing=None):
    clauses, params = [], []
    if decision:
        clauses.append("routing_decision = %s")
        params.append(decision)
    if facility_id is not None:
        clauses.append("facility_id = %s")
        params.append(facility_id)
    if search:
        clauses.append("(patient_id ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s)")
        s = f"%{search}%"
        params += [s, s, s]
    if eligible is not None:
        clauses.append("has_active_mcb = %s")
        params.append(eligible)
    if new_admission is not None:
        clauses.append("is_new_admission = %s")
        params.append(new_admission)
    if missing:
        clauses.append("missing_fields @> %s")
        params.append(Jsonb([missing]))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT * FROM patient_eligibility" + where +
        " ORDER BY routing_decision, extraction_confidence DESC, patient_id"
    )
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_detail(patient_id):
    """Full evidence bundle for one patient so a biller can verify every routed
    field against its source: the verdict, the wound extractions behind it, and
    the RAW source records (coverage, diagnoses, assessments, notes).

    Two-key data model (see API.md): coverage/diagnoses key on the string
    patient_id (FA-001); notes/assessments key on the integer internal_id.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM patient_eligibility WHERE patient_id = %s",
                    (patient_id,))
        result = cur.fetchone()
        if not result:
            return None
        pid_str, pid_int = result["patient_id"], result["internal_id"]

        cur.execute(
            "SELECT * FROM wound_extractions WHERE patient_id = %s "
            "ORDER BY is_primary DESC, confidence DESC",
            (pid_int,),
        )
        extractions = cur.fetchall()

        def raws(table, key):
            cur.execute(f"SELECT raw FROM {table} WHERE patient_id = %s ORDER BY id",
                        (key,))
            return [r["raw"] for r in cur.fetchall()]

        return {
            "result": result,
            "extractions": extractions,
            "coverage": raws("coverage", pid_str),
            "diagnoses": raws("diagnoses", pid_str),
            "assessments": raws("assessments", pid_int),
            "notes": raws("notes", pid_int),
        }


def summary(conn=None):
    with _session(conn) as c, c.cursor() as cur:
        def one(sql):
            cur.execute(sql)
            return cur.fetchall()

        total = one("SELECT COUNT(*) n FROM patient_eligibility")[0]["n"]
        decisions = {
            r["routing_decision"]: r["n"]
            for r in one("SELECT routing_decision, COUNT(*) n FROM patient_eligibility "
                         "GROUP BY 1 ORDER BY 2 DESC")
        }
        mcb = one("SELECT COUNT(*) n FROM patient_eligibility WHERE has_active_mcb")[0]["n"]
        by_fac = {
            r["facility_id"]: {"auto": r["a"], "flag": r["f"], "reject": r["rj"]}
            for r in one(
                """SELECT facility_id,
                     COUNT(*) FILTER (WHERE routing_decision='auto_accept') a,
                     COUNT(*) FILTER (WHERE routing_decision='flag_for_review') f,
                     COUNT(*) FILTER (WHERE routing_decision='reject') rj
                   FROM patient_eligibility GROUP BY 1 ORDER BY 1"""
            )
        }
        review_flags = {
            r["f"]: r["n"]
            for r in one(
                "SELECT jsonb_array_elements_text(flags) f, COUNT(*) n "
                "FROM patient_eligibility WHERE routing_decision='flag_for_review' "
                "GROUP BY 1 ORDER BY 2 DESC"
            )
        }
        return {
            "total_patients": total,
            "active_mcb": mcb,
            "decisions": decisions,
            "by_facility": by_fac,
            "review_flags": review_flags,
        }
