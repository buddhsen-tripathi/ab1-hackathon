from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from billready.config import DB_PATH


class CacheStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS api_cache (
                    cache_key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sync_meta (
                    meta_key TEXT PRIMARY KEY,
                    meta_value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS eligibility_results (
                    patient_id TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    computed_at TEXT NOT NULL
                );
                """
            )

    def get(self, cache_key: str) -> list | dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT response_json FROM api_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["response_json"])

    def set(self, cache_key: str, data: list | dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO api_cache (cache_key, response_json, fetched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json = excluded.response_json,
                    fetched_at = excluded.fetched_at
                """,
                (cache_key, json.dumps(data), now),
            )

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_meta (meta_key, meta_value) VALUES (?, ?)
                ON CONFLICT(meta_key) DO UPDATE SET meta_value = excluded.meta_value
                """,
                (key, value),
            )

    def get_meta(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT meta_value FROM sync_meta WHERE meta_key = ?",
                (key,),
            ).fetchone()
        return row["meta_value"] if row else None

    def save_eligibility_results(self, results: list[dict]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for result in results:
                conn.execute(
                    """
                    INSERT INTO eligibility_results (patient_id, result_json, computed_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(patient_id) DO UPDATE SET
                        result_json = excluded.result_json,
                        computed_at = excluded.computed_at
                    """,
                    (result["patient_id"], json.dumps(result), now),
                )

    def clear_cache(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM api_cache")

    def load_eligibility_results(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT result_json FROM eligibility_results ORDER BY patient_id"
            ).fetchall()
        return [json.loads(row["result_json"]) for row in rows]

    def get_patient_notes(self, internal_id: int) -> list[dict]:
        cached = self.get(f"notes:{internal_id}")
        return cached if cached else []

    def get_patient_assessments(self, internal_id: int) -> list[dict]:
        cached = self.get(f"assessments:{internal_id}")
        return cached if cached else []

    def get_patient_coverage(self, patient_id: str) -> list[dict]:
        cached = self.get(f"coverage:{patient_id}")
        return cached if cached else []

    def get_patient_diagnoses(self, patient_id: str) -> list[dict]:
        cached = self.get(f"diagnoses:{patient_id}")
        return cached if cached else []

    def get_cache_stats(self) -> dict:
        with self._connect() as conn:
            cache_count = conn.execute("SELECT COUNT(*) FROM api_cache").fetchone()[0]
            result_count = conn.execute("SELECT COUNT(*) FROM eligibility_results").fetchone()[0]
            last_sync = conn.execute(
                "SELECT meta_value FROM sync_meta WHERE meta_key = 'last_full_sync'"
            ).fetchone()
            last_run = conn.execute(
                "SELECT meta_value FROM sync_meta WHERE meta_key = 'last_pipeline_run'"
            ).fetchone()
        return {
            "cached_endpoints": cache_count,
            "eligibility_rows": result_count,
            "last_full_sync": last_sync["meta_value"] if last_sync else None,
            "last_pipeline_run": json.loads(last_run["meta_value"]) if last_run else None,
        }
