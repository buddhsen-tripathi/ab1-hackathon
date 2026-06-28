import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "claimlens.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            internal_id INTEGER UNIQUE,
            facility_id INTEGER,
            facility_name TEXT,
            first_name TEXT,
            last_name TEXT,
            birth_date TEXT,
            gender TEXT,
            primary_payer_code TEXT,
            is_new_admission INTEGER DEFAULT 0,

            has_medicare_part_b INTEGER DEFAULT 0,
            coverage_effective_from TEXT,
            coverage_effective_to TEXT,
            coverage_payer_name TEXT,

            diagnoses TEXT,

            wound_type TEXT,
            wound_location TEXT,
            wound_stage TEXT,
            length_cm REAL,
            width_cm REAL,
            depth_cm REAL,
            drainage TEXT,
            is_multi_wound INTEGER DEFAULT 0,
            all_wounds TEXT,

            evidence_trace TEXT,
            extraction_source TEXT,
            extraction_confidence REAL DEFAULT 0,
            note_format TEXT,

            claim_score INTEGER DEFAULT 0,
            routing_decision TEXT,
            missing_fields TEXT,
            score_breakdown TEXT,
            biller_action TEXT,
            missing_doc_request TEXT,
            routing_reason TEXT,
            summary_narrative TEXT,
            summary_generated_by TEXT,

            raw_notes TEXT,
            raw_assessments TEXT,
            processed_at TEXT,
            sync_version INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS api_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT,
            status_code INTEGER,
            retries INTEGER DEFAULT 0,
            retry_after_seconds INTEGER DEFAULT 0,
            timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    # Lightweight migrations for existing local databases.
    existing = {row[1] for row in conn.execute("PRAGMA table_info(patients)").fetchall()}
    for column, definition in {
        "summary_narrative": "TEXT",
        "summary_generated_by": "TEXT",
    }.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE patients ADD COLUMN {column} {definition}")
    conn.commit()
    conn.close()


def upsert_patient(data: dict):
    conn = get_conn()
    cols = list(data.keys())
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "patient_id")
    sql = f"""
        INSERT INTO patients ({', '.join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(patient_id) DO UPDATE SET {updates}
    """
    conn.execute(sql, list(data.values()))
    conn.commit()
    conn.close()


def log_api_request(endpoint: str, status_code: int, retries: int = 0, retry_after: int = 0):
    conn = get_conn()
    conn.execute(
        "INSERT INTO api_requests (endpoint, status_code, retries, retry_after_seconds, timestamp) VALUES (?,?,?,?,?)",
        (endpoint, status_code, retries, retry_after, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_api_health():
    conn = get_conn()
    row = conn.execute("""
        SELECT
            COUNT(*) as total_requests,
            SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) as total_429s,
            SUM(retries) as total_retries,
            SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) as failed_requests,
            AVG(CASE WHEN retry_after_seconds > 0 THEN retry_after_seconds END) as avg_retry_delay
        FROM api_requests
    """).fetchone()
    conn.close()
    return dict(row)


def get_all_patients(routing_decision=None, facility_id=None):
    conn = get_conn()
    sql = "SELECT * FROM patients WHERE 1=1"
    params = []
    if routing_decision:
        sql += " AND routing_decision = ?"
        params.append(routing_decision)
    if facility_id:
        sql += " AND facility_id = ?"
        params.append(facility_id)
    sql += " ORDER BY claim_score DESC"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


def get_patient(patient_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_patient_summary(patient_id: str, summary: str, generated_by: str):
    conn = get_conn()
    conn.execute(
        "UPDATE patients SET summary_narrative = ?, summary_generated_by = ? WHERE patient_id = ?",
        (summary, generated_by, patient_id),
    )
    conn.commit()
    conn.close()


def get_stats():
    conn = get_conn()
    row = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN routing_decision = 'auto_accept' THEN 1 ELSE 0 END) as auto_accept,
            SUM(CASE WHEN routing_decision = 'flag_for_review' THEN 1 ELSE 0 END) as flag_for_review,
            SUM(CASE WHEN routing_decision = 'reject' THEN 1 ELSE 0 END) as reject,
            SUM(CASE WHEN missing_fields IS NOT NULL AND missing_fields != '[]' THEN 1 ELSE 0 END) as docs_gap_count,
            SUM(CASE WHEN has_medicare_part_b = 1 THEN 1 ELSE 0 END) as medicare_b_count,
            AVG(CASE WHEN extraction_confidence > 0 THEN extraction_confidence ELSE NULL END) as avg_confidence
        FROM patients
    """).fetchone()
    conn.close()
    return dict(row)


def set_sync_state(key: str, value: str):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO sync_state (key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


def get_sync_state(key: str):
    conn = get_conn()
    row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None
