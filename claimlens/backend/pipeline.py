"""
Async data ingestion pipeline for PCC API.
Handles rate limiting with Retry-After-aware retry logic.
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Callable

import httpx

from db import init_db, upsert_patient, log_api_request, set_sync_state, get_sync_state
from extractor import (
    extract_from_assessment, extract_from_note_regex, extract_from_note_llm,
    merge_extractions, detect_multi_wound, select_primary_wound, wound_type_from_icd10
)
from scorer import compute_claim_score

BASE_URL = "https://hackathon.prod.pulsefoundry.ai"
FACILITIES = [
    {"facility_id": 101, "name": "Facility A"},
    {"facility_id": 102, "name": "Facility B"},
    {"facility_id": 103, "name": "Facility C"},
]
MAX_RETRIES = 8
CONCURRENCY = 10  # Max concurrent API requests

# Global sync state
sync_progress = {
    "running": False,
    "total": 0,
    "processed": 0,
    "errors": 0,
    "started_at": None,
    "status": "idle",
    "current_step": "",
}


async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    progress_cb: Optional[Callable] = None
) -> Optional[dict]:
    """Fetch URL with Retry-After-aware exponential backoff."""
    retries = 0
    last_status = 0
    retry_after_used = 0

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.get(url, params=params, timeout=30.0)
            last_status = response.status_code

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "3"))
                retry_after_used = max(retry_after_used, retry_after)
                retries += 1
                log_api_request(url, 429, retries, retry_after)
                await asyncio.sleep(retry_after)
                continue

            if response.status_code == 200:
                log_api_request(url, 200, retries, retry_after_used)
                return response.json()

            # Other errors
            log_api_request(url, response.status_code, retries, 0)
            return None

        except Exception as e:
            retries += 1
            wait = min(2 ** attempt, 30)
            await asyncio.sleep(wait)

    log_api_request(url, last_status or 0, retries, retry_after_used)
    return None


async def process_patient(
    client: httpx.AsyncClient,
    patient: dict,
    semaphore: asyncio.Semaphore,
    use_llm: bool = True,
) -> None:
    """Fetch all data for one patient and compute claim readiness."""
    async with semaphore:
        patient_id = patient["patient_id"]
        internal_id = patient["id"]
        facility_id = patient["facility_id"]

        # Parallel fetch: coverage + diagnoses + notes + assessments
        coverage_task = asyncio.create_task(
            fetch_with_retry(client, f"{BASE_URL}/pcc/coverage", {"patient_id": patient_id})
        )
        diagnoses_task = asyncio.create_task(
            fetch_with_retry(client, f"{BASE_URL}/pcc/diagnoses", {"patient_id": patient_id})
        )
        notes_task = asyncio.create_task(
            fetch_with_retry(client, f"{BASE_URL}/pcc/notes", {"patient_id": internal_id})
        )
        assessments_task = asyncio.create_task(
            fetch_with_retry(client, f"{BASE_URL}/pcc/assessments", {"patient_id": internal_id})
        )

        coverage_data, diagnoses_data, notes_data, assessments_data = await asyncio.gather(
            coverage_task, diagnoses_task, notes_task, assessments_task
        )

        coverage_data = coverage_data or []
        diagnoses_data = diagnoses_data or []
        notes_data = notes_data or []
        assessments_data = assessments_data or []

        # --- Coverage analysis ---
        has_mcb = False
        mcb_from = None
        mcb_to = None
        mcb_payer_name = None
        for cov in coverage_data:
            payer_type = (cov.get("payer_type") or "").lower()
            payer_code = (cov.get("payer_code") or "").upper()
            if payer_code == "MCB" or "medicare b" in payer_type:
                eff_to = cov.get("effective_to")
                # Active if effective_to is null (no end date)
                if eff_to is None:
                    has_mcb = True
                    mcb_from = cov.get("effective_from")
                    mcb_to = eff_to
                    mcb_payer_name = cov.get("payer_name") or "Medicare Part B"
                    break

        # --- Wound extraction ---
        # Priority: assessments > structured notes > LLM notes
        assessment_extraction = {}
        for a in assessments_data:
            if a.get("raw_json") and a.get("status") == "Complete":
                result = extract_from_assessment(a)
                if result.get("wound_type"):
                    assessment_extraction = result
                    break

        # Try structured note extraction
        note_extraction = {}
        note_format = "unknown"
        for n in (notes_data or []):
            result = extract_from_note_regex(n)
            if result.get("wound_type") or result.get("length_cm"):
                note_extraction = result
                note_format = result.get("note_format", "prose")
                break

        # If note extraction weak and LLM enabled, try LLM
        if use_llm and (not note_extraction.get("wound_type") or note_extraction.get("confidence", 0) < 0.7):
            for n in (notes_data or []):
                text = n.get("note_text") or ""
                if len(text) > 50 and not note_extraction.get("wound_type"):
                    llm_result = await extract_from_note_llm(n)
                    if llm_result.get("wound_type"):
                        note_extraction = llm_result
                        note_format = "envive"
                        break

        # Merge
        merged = merge_extractions(assessment_extraction, note_extraction)

        # ICD-10 fallback for wound type
        if not merged.get("wound_type") and diagnoses_data:
            icd_wtype = wound_type_from_icd10(diagnoses_data)
            if icd_wtype:
                merged["wound_type"] = icd_wtype
                ev = merged.get("evidence") or {}
                ev["wound_type"] = f"Derived from ICD-10 diagnosis code"
                merged["evidence"] = ev

        # Multi-wound detection
        multi_wounds = detect_multi_wound(notes_data or [])
        is_multi_wound = len(multi_wounds) > 0
        all_wounds_json = json.dumps(multi_wounds) if multi_wounds else None

        # If multi-wound, use primary wound
        if multi_wounds and not merged.get("wound_type"):
            primary = select_primary_wound(multi_wounds)
            if primary:
                merged.update(primary)

        # Build patient record
        facility_names = {101: "Facility A", 102: "Facility B", 103: "Facility C"}
        record = {
            "patient_id": patient_id,
            "internal_id": internal_id,
            "facility_id": facility_id,
            "facility_name": facility_names.get(facility_id, f"Facility {facility_id}"),
            "first_name": patient.get("first_name"),
            "last_name": patient.get("last_name"),
            "birth_date": patient.get("birth_date"),
            "gender": patient.get("gender"),
            "primary_payer_code": patient.get("primary_payer_code"),
            "is_new_admission": 1 if patient.get("is_new_admission") else 0,
            "has_medicare_part_b": 1 if has_mcb else 0,
            "coverage_effective_from": mcb_from,
            "coverage_effective_to": mcb_to,
            "coverage_payer_name": mcb_payer_name,
            "diagnoses": json.dumps(diagnoses_data),
            "wound_type": merged.get("wound_type"),
            "wound_location": merged.get("wound_location"),
            "wound_stage": merged.get("wound_stage"),
            "length_cm": merged.get("length_cm"),
            "width_cm": merged.get("width_cm"),
            "depth_cm": merged.get("depth_cm"),
            "drainage": merged.get("drainage"),
            "is_multi_wound": 1 if is_multi_wound else 0,
            "all_wounds": all_wounds_json,
            "evidence_trace": json.dumps(merged.get("evidence", {})),
            "extraction_source": merged.get("source"),
            "extraction_confidence": merged.get("confidence", 0),
            "note_format": note_format,
            "raw_notes": json.dumps([n.get("note_text", "")[:500] for n in (notes_data or [])[:3]]),
            "raw_assessments": json.dumps(assessments_data[:2]),
            "processed_at": datetime.utcnow().isoformat(),
        }

        # Score
        scoring = compute_claim_score({
            **record,
            "has_medicare_part_b": has_mcb,
        })
        record.update({
            "claim_score": scoring["claim_score"],
            "routing_decision": scoring["routing_decision"],
            "missing_fields": json.dumps(scoring["missing_fields"]),
            "score_breakdown": json.dumps(scoring["score_breakdown"]),
            "biller_action": scoring["biller_action"],
            "routing_reason": scoring["routing_reason"],
            "missing_doc_request": scoring.get("missing_doc_request"),
        })

        upsert_patient(record)


async def run_sync(use_llm: bool = True, progress_cb: Optional[Callable] = None):
    """Main sync pipeline: fetch all patients from all facilities and process them."""
    global sync_progress

    sync_progress.update({
        "running": True,
        "total": 0,
        "processed": 0,
        "errors": 0,
        "started_at": datetime.utcnow().isoformat(),
        "status": "running",
        "current_step": "Fetching patient lists...",
    })

    init_db()
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient() as client:
        # Fetch patient lists from all facilities
        all_patients = []
        for facility in FACILITIES:
            patients = await fetch_with_retry(
                client,
                f"{BASE_URL}/pcc/patients",
                {"facility_id": facility["facility_id"]}
            )
            if patients:
                all_patients.extend(patients)
                sync_progress["current_step"] = f"Loaded {len(all_patients)} patients so far..."

        sync_progress["total"] = len(all_patients)
        sync_progress["current_step"] = f"Processing {len(all_patients)} patients..."

        # Process all patients concurrently (with semaphore limiting)
        tasks = []
        for patient in all_patients:
            task = asyncio.create_task(
                _process_with_progress(client, patient, semaphore, use_llm)
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    set_sync_state("last_sync", datetime.utcnow().isoformat())
    sync_progress.update({
        "running": False,
        "status": "complete",
        "current_step": f"Sync complete. Processed {sync_progress['processed']} patients.",
    })


async def _process_with_progress(client, patient, semaphore, use_llm):
    global sync_progress
    try:
        await process_patient(client, patient, semaphore, use_llm)
        sync_progress["processed"] += 1
    except Exception as e:
        sync_progress["errors"] += 1
        print(f"Error processing {patient.get('patient_id')}: {e}")
