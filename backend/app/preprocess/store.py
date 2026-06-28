"""Persistence for the preprocessing output (`wound_extractions` table).

Owns its own table so it doesn't collide with the raw-ingestion db.py schema.
A full preprocess run truncates and re-inserts (the rows are derived; cheap to
rebuild). Incremental rebuild can come later alongside the `since` sync.
"""
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
CREATE TABLE IF NOT EXISTS wound_extractions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id BIGINT,
    source_doc TEXT,
    source_doc_id BIGINT,
    source_format TEXT,
    method TEXT,
    wound_index INTEGER,
    is_primary BOOLEAN,
    wound_type TEXT,
    stage TEXT,
    location TEXT,
    laterality TEXT,
    length_cm REAL,
    width_cm REAL,
    depth_cm REAL,
    area_cm2 REAL,
    drainage_amount TEXT,
    drainage_type TEXT,
    has_all_measurements BOOLEAN,
    billing_ready BOOLEAN,
    confidence REAL,
    flags JSONB,
    raw_span TEXT,
    extra JSONB
);
CREATE INDEX IF NOT EXISTS idx_we_patient ON wound_extractions(patient_id);
CREATE INDEX IF NOT EXISTS idx_we_format ON wound_extractions(source_format);
"""

_COLS = [
    "patient_id", "source_doc", "source_doc_id", "source_format", "method",
    "wound_index", "is_primary", "wound_type", "stage", "location", "laterality",
    "length_cm", "width_cm", "depth_cm", "area_cm2", "drainage_amount",
    "drainage_type", "has_all_measurements", "billing_ready", "confidence",
    "flags", "raw_span", "extra",
]
_JSONB_COLS = {"flags", "extra"}


def init(conn=None):
    with _session(conn) as c, c.cursor() as cur:
        cur.execute(DDL)


def _to_params(row):
    out = []
    for c in _COLS:
        v = row.get(c)
        out.append(Jsonb(v) if c in _JSONB_COLS else v)
    return out


def replace_all(rows, conn=None):
    # Single multi-row INSERT per chunk = one round-trip per chunk (executemany
    # round-trips per row, which is painfully slow over Neon).
    cols_sql = ",".join(_COLS)
    one = "(" + ",".join(["%s"] * len(_COLS)) + ")"
    chunk = max(1, 30000 // len(_COLS))
    with _session(conn) as c, c.cursor() as cur:
        cur.execute("TRUNCATE wound_extractions RESTART IDENTITY")
        for i in range(0, len(rows), chunk):
            batch = rows[i:i + chunk]
            values_sql = ",".join([one] * len(batch))
            params = [p for r in batch for p in _to_params(r)]
            cur.execute(
                f"INSERT INTO wound_extractions ({cols_sql}) VALUES {values_sql}",
                params,
            )


def summary(conn=None):
    with _session(conn) as c, c.cursor() as cur:
        def one(sql):
            cur.execute(sql)
            return cur.fetchall()

        total = one("SELECT COUNT(*) n FROM wound_extractions")[0]["n"]
        by_fmt = {
            r["source_format"]: r["n"]
            for r in one("SELECT source_format, COUNT(*) n FROM wound_extractions "
                         "GROUP BY 1 ORDER BY 2 DESC")
        }
        billing = one("SELECT COUNT(*) n FROM wound_extractions WHERE billing_ready")[0]["n"]
        primary = one("SELECT COUNT(*) n FROM wound_extractions WHERE is_primary")[0]["n"]
        # NULLIF guards against division-by-zero on an empty table.
        coverage = one(
            """SELECT
                 COALESCE(ROUND(100.0*COUNT(*) FILTER (WHERE wound_type IS NOT NULL)/NULLIF(COUNT(*),0),1),0) wound_type,
                 COALESCE(ROUND(100.0*COUNT(*) FILTER (WHERE length_cm IS NOT NULL)/NULLIF(COUNT(*),0),1),0) length,
                 COALESCE(ROUND(100.0*COUNT(*) FILTER (WHERE width_cm IS NOT NULL)/NULLIF(COUNT(*),0),1),0) width,
                 COALESCE(ROUND(100.0*COUNT(*) FILTER (WHERE depth_cm IS NOT NULL)/NULLIF(COUNT(*),0),1),0) depth,
                 COALESCE(ROUND(100.0*COUNT(*) FILTER (WHERE drainage_amount IS NOT NULL)/NULLIF(COUNT(*),0),1),0) drainage
               FROM wound_extractions"""
        )[0]
        flags = {
            r["f"]: r["n"]
            for r in one(
                "SELECT jsonb_array_elements_text(flags) f, COUNT(*) n "
                "FROM wound_extractions GROUP BY 1 ORDER BY 2 DESC"
            )
        }
        methods = {
            r["method"]: r["n"]
            for r in one("SELECT method, COUNT(*) n FROM wound_extractions "
                         "GROUP BY 1 ORDER BY 2 DESC")
        }
        avg_conf = one(
            "SELECT COALESCE(ROUND(AVG(confidence)::numeric, 3), 0) c "
            "FROM wound_extractions"
        )[0]["c"]
        return {
            "total_wound_rows": total,
            "primary_wounds": primary,
            "billing_ready": billing,
            "billing_ready_pct": round(100 * billing / total, 1) if total else 0,
            "by_source_format": by_fmt,
            "field_coverage_pct": {k: float(v) for k, v in coverage.items()},
            "flag_distribution": flags,
            "method_distribution": methods,
            "avg_confidence": float(avg_conf),
        }
