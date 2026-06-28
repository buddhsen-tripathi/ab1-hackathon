"""Neon Postgres storage via psycopg3.

Full-fidelity raw record kept per row as JSONB; a few hot columns promoted
for easy querying. Upserts use INSERT ... ON CONFLICT (id) DO UPDATE so
re-ingestion is idempotent.
"""
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import DATABASE_URL

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS patients (
        id BIGINT PRIMARY KEY,
        patient_id TEXT,
        facility_id INTEGER,
        primary_payer_code TEXT,
        is_new_admission BOOLEAN,
        last_modified_at TEXT,
        raw JSONB
    )""",
    """CREATE TABLE IF NOT EXISTS diagnoses (
        id BIGINT PRIMARY KEY,
        patient_id TEXT,
        icd10_code TEXT,
        icd10_description TEXT,
        clinical_status TEXT,
        raw JSONB
    )""",
    """CREATE TABLE IF NOT EXISTS coverage (
        id BIGINT PRIMARY KEY,
        patient_id TEXT,
        payer_code TEXT,
        payer_type TEXT,
        effective_to TEXT,
        raw JSONB
    )""",
    """CREATE TABLE IF NOT EXISTS notes (
        id BIGINT PRIMARY KEY,
        patient_id BIGINT,
        note_type TEXT,
        effective_date TEXT,
        note_text TEXT,
        raw JSONB
    )""",
    """CREATE TABLE IF NOT EXISTS assessments (
        id BIGINT PRIMARY KEY,
        patient_id BIGINT,
        assessment_type TEXT,
        status TEXT,
        raw_json TEXT,
        raw JSONB
    )""",
    "CREATE INDEX IF NOT EXISTS idx_diag_pid ON diagnoses(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_cov_pid ON coverage(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_notes_pid ON notes(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_assess_pid ON assessments(patient_id)",
]


def connect():
    """Open a Neon connection. Rows come back as dicts.

    prepare_threshold=None disables server-side prepared statements, which the
    pooled (pgbouncer transaction-mode) endpoint does not support.
    """
    return psycopg.connect(
        DATABASE_URL, row_factory=dict_row, prepare_threshold=None
    )


def init():
    with connect() as conn:
        with conn.cursor() as cur:
            for stmt in SCHEMA:
                cur.execute(stmt)
        conn.commit()


def _executemany(conn, sql, rows):
    if not rows:
        return
    with conn.cursor() as cur:
        cur.executemany(sql, rows)


def upsert_patients(conn, patients):
    sql = """INSERT INTO patients
        (id, patient_id, facility_id, primary_payer_code, is_new_admission,
         last_modified_at, raw)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO UPDATE SET
            patient_id=EXCLUDED.patient_id,
            facility_id=EXCLUDED.facility_id,
            primary_payer_code=EXCLUDED.primary_payer_code,
            is_new_admission=EXCLUDED.is_new_admission,
            last_modified_at=EXCLUDED.last_modified_at,
            raw=EXCLUDED.raw"""
    rows = [
        (
            p["id"],
            p.get("patient_id"),
            p.get("facility_id"),
            p.get("primary_payer_code"),
            bool(p.get("is_new_admission")),
            p.get("last_modified_at"),
            Jsonb(p),
        )
        for p in patients
    ]
    _executemany(conn, sql, rows)
    conn.commit()


def upsert_bundle(conn, diagnoses, coverage, notes, assessments):
    _executemany(
        conn,
        """INSERT INTO diagnoses
            (id, patient_id, icd10_code, icd10_description, clinical_status, raw)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                patient_id=EXCLUDED.patient_id,
                icd10_code=EXCLUDED.icd10_code,
                icd10_description=EXCLUDED.icd10_description,
                clinical_status=EXCLUDED.clinical_status,
                raw=EXCLUDED.raw""",
        [
            (
                d["id"],
                d.get("patient_id"),
                d.get("icd10_code"),
                d.get("icd10_description"),
                d.get("clinical_status"),
                Jsonb(d),
            )
            for d in diagnoses
        ],
    )
    _executemany(
        conn,
        """INSERT INTO coverage
            (id, patient_id, payer_code, payer_type, effective_to, raw)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                patient_id=EXCLUDED.patient_id,
                payer_code=EXCLUDED.payer_code,
                payer_type=EXCLUDED.payer_type,
                effective_to=EXCLUDED.effective_to,
                raw=EXCLUDED.raw""",
        [
            (
                c["id"],
                c.get("patient_id"),
                c.get("payer_code"),
                c.get("payer_type"),
                c.get("effective_to"),
                Jsonb(c),
            )
            for c in coverage
        ],
    )
    _executemany(
        conn,
        """INSERT INTO notes
            (id, patient_id, note_type, effective_date, note_text, raw)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                patient_id=EXCLUDED.patient_id,
                note_type=EXCLUDED.note_type,
                effective_date=EXCLUDED.effective_date,
                note_text=EXCLUDED.note_text,
                raw=EXCLUDED.raw""",
        [
            (
                n["id"],
                n.get("patient_id"),
                n.get("note_type"),
                n.get("effective_date"),
                n.get("note_text"),
                Jsonb(n),
            )
            for n in notes
        ],
    )
    _executemany(
        conn,
        """INSERT INTO assessments
            (id, patient_id, assessment_type, status, raw_json, raw)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                patient_id=EXCLUDED.patient_id,
                assessment_type=EXCLUDED.assessment_type,
                status=EXCLUDED.status,
                raw_json=EXCLUDED.raw_json,
                raw=EXCLUDED.raw""",
        [
            (
                a["id"],
                a.get("patient_id"),
                a.get("assessment_type"),
                a.get("status"),
                a.get("raw_json"),
                Jsonb(a),
            )
            for a in assessments
        ],
    )
    conn.commit()


def counts(conn):
    out = {}
    for tbl in ("patients", "diagnoses", "coverage", "notes", "assessments"):
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {tbl}")
            out[tbl] = cur.fetchone()["n"]
    return out


def truncate(conn):
    """Wipe all ingested data (keeps the schema). Returns rows removed."""
    before = sum(counts(conn).values())
    with conn.cursor() as cur:
        cur.execute("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY")
    conn.commit()
    return before


def fetch_patients(facility_id=None):
    with connect() as conn, conn.cursor() as cur:
        if facility_id is not None:
            cur.execute(
                "SELECT raw FROM patients WHERE facility_id=%s ORDER BY id",
                (facility_id,),
            )
        else:
            cur.execute("SELECT raw FROM patients ORDER BY id")
        return [r["raw"] for r in cur.fetchall()]


# ---- Generic table browsing (for the DB viewer) ----------------------------

TABLES = ("patients", "diagnoses", "coverage", "notes", "assessments")


def list_tables():
    """Return row counts per table (drives the table picker)."""
    with connect() as conn:
        return counts(conn)


def _typename(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, (dict, list)):
        return "json"
    return "str"


def _infer_columns(rows):
    """Ordered column list with an inferred type, from the union of row keys."""
    order, seen, types = [], set(), {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            if k not in seen:
                seen.add(k)
                order.append(k)
            if v is not None and k not in types:
                types[k] = _typename(v)
    return [{"name": k, "type": types.get(k, "str")} for k in order]


def fetch_table(name, limit=50, offset=0, search=None, facility_id=None):
    """Paginated view of a table's original records (the `raw` JSONB payload).

    search   = case-insensitive substring across the whole row (raw::text ILIKE)
    facility_id = only applies to the patients table (the one with that column)
    """
    if name not in TABLES:
        raise ValueError(f"unknown table: {name}")
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    clauses, params = [], []
    if search:
        clauses.append("raw::text ILIKE %s")
        params.append(f"%{search}%")
    if facility_id is not None and name == "patients":
        clauses.append("facility_id = %s")
        params.append(facility_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM {name}{where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"SELECT raw FROM {name}{where} ORDER BY id LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        rows = [r["raw"] for r in cur.fetchall()]
    return {
        "table": name,
        "total": total,
        "limit": limit,
        "offset": offset,
        "columns": _infer_columns(rows),
        "rows": rows,
    }
