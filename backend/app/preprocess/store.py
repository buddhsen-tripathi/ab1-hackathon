"""Persistence for the preprocessing output (`wound_extractions` table).

Owns its own table so it doesn't collide with the raw-ingestion db.py schema.
A full preprocess run truncates and re-inserts (the rows are derived; cheap to
rebuild). Incremental rebuild can come later alongside the `since` sync.
"""
from psycopg.types.json import Jsonb

from ..db import connect

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


def init():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()


def _to_params(row):
    out = []
    for c in _COLS:
        v = row.get(c)
        out.append(Jsonb(v) if c in _JSONB_COLS else v)
    return out


def replace_all(rows):
    placeholders = ",".join(["%s"] * len(_COLS))
    sql = f"INSERT INTO wound_extractions ({','.join(_COLS)}) VALUES ({placeholders})"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE wound_extractions RESTART IDENTITY")
            cur.executemany(sql, [_to_params(r) for r in rows])
        conn.commit()


def summary():
    with connect() as conn, conn.cursor() as cur:
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
        coverage = one(
            """SELECT
                 ROUND(100.0*COUNT(*) FILTER (WHERE wound_type IS NOT NULL)/COUNT(*),1) wound_type,
                 ROUND(100.0*COUNT(*) FILTER (WHERE length_cm IS NOT NULL)/COUNT(*),1) length,
                 ROUND(100.0*COUNT(*) FILTER (WHERE width_cm IS NOT NULL)/COUNT(*),1) width,
                 ROUND(100.0*COUNT(*) FILTER (WHERE depth_cm IS NOT NULL)/COUNT(*),1) depth,
                 ROUND(100.0*COUNT(*) FILTER (WHERE drainage_amount IS NOT NULL)/COUNT(*),1) drainage
               FROM wound_extractions"""
        )[0]
        flags = {
            r["f"]: r["n"]
            for r in one(
                "SELECT jsonb_array_elements_text(flags) f, COUNT(*) n "
                "FROM wound_extractions GROUP BY 1 ORDER BY 2 DESC"
            )
        }
        return {
            "total_wound_rows": total,
            "primary_wounds": primary,
            "billing_ready": billing,
            "billing_ready_pct": round(100 * billing / total, 1) if total else 0,
            "by_source_format": by_fmt,
            "field_coverage_pct": {k: float(v) for k, v in coverage.items()},
            "flag_distribution": flags,
        }
