from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from collections.abc import Callable

from billready.api.client import PCCClient
from billready.config import FACILITY_IDS
from billready.models import PatientRecord
from billready.storage.cache import CacheStore

logger = logging.getLogger(__name__)


async def fetch_all_patients(client: PCCClient, cache: CacheStore) -> list[dict]:
    patients: list[dict] = []
    for facility_id in FACILITY_IDS:
        key = f"patients:facility={facility_id}"
        cached = cache.get(key)
        if cached is not None:
            patients.extend(cached)
            continue

        data = await client.get_json("/pcc/patients", {"facility_id": facility_id})
        cache.set(key, data)
        patients.extend(data)
        logger.info("Fetched %d patients from facility %s", len(data), facility_id)

    return patients


async def _fetch_patient_detail(
    client: PCCClient,
    cache: CacheStore,
    patient: dict,
) -> PatientRecord:
    internal_id = patient["id"]
    pcc_id = patient["patient_id"]

    async def get_cached(endpoint: str, key: str, params: dict) -> list:
        cached = cache.get(key)
        if cached is not None:
            return cached
        data = await client.get_json(endpoint, params)
        if not isinstance(data, list):
            data = [data]
        cache.set(key, data)
        return data

    diagnoses, coverage, notes, assessments = await asyncio.gather(
        get_cached("/pcc/diagnoses", f"diagnoses:{pcc_id}", {"patient_id": pcc_id}),
        get_cached("/pcc/coverage", f"coverage:{pcc_id}", {"patient_id": pcc_id}),
        get_cached("/pcc/notes", f"notes:{internal_id}", {"patient_id": internal_id}),
        get_cached("/pcc/assessments", f"assessments:{internal_id}", {"patient_id": internal_id}),
    )

    return PatientRecord(
        internal_id=internal_id,
        patient_id=pcc_id,
        facility_id=patient["facility_id"],
        first_name=patient.get("first_name"),
        last_name=patient.get("last_name"),
        primary_payer_code=patient.get("primary_payer_code"),
        is_new_admission=bool(patient.get("is_new_admission")),
        diagnoses=diagnoses,
        coverage=coverage,
        notes=notes,
        assessments=assessments,
    )


async def ingest_all(
    client: PCCClient,
    cache: CacheStore,
    on_progress: Callable[[str, str, int], None] | None = None,
) -> list[PatientRecord]:
    if on_progress:
        on_progress("ingest", "Fetching patient lists from PCC (3 facilities)…", 10)

    patients = await fetch_all_patients(client, cache)
    logger.info("Loading details for %d patients...", len(patients))

    if on_progress:
        on_progress("ingest", f"Fetching clinical data for {len(patients)} patients…", 20)

    records: list[PatientRecord] = []
    total = len(patients)
    batch_size = 25

    for i in range(0, total, batch_size):
        batch = patients[i : i + batch_size]
        batch_records = await asyncio.gather(
            *[_fetch_patient_detail(client, cache, p) for p in batch]
        )
        records.extend(batch_records)
        loaded = len(records)
        pct = 20 + int(50 * loaded / max(total, 1))
        if on_progress:
            on_progress(
                "ingest",
                f"Ingested {loaded}/{total} patients (notes, coverage, assessments)",
                pct,
            )

    cache.set_meta("last_full_sync", datetime.now(timezone.utc).isoformat())
    if on_progress:
        on_progress("ingest", f"Ingestion complete — {total} patients loaded", 72)
    return records
