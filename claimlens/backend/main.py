"""ClaimLens AI — FastAPI backend."""
import asyncio
import json
import os
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from db import init_db, get_all_patients, get_patient, get_stats, get_api_health, get_sync_state
from pipeline import run_sync, sync_progress

app = FastAPI(title="ClaimLens AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


def _parse_json_fields(p: dict) -> dict:
    """Parse JSON string fields back to Python objects."""
    for field in ["evidence_trace", "score_breakdown", "missing_fields", "diagnoses", "raw_assessments"]:
        if isinstance(p.get(field), str):
            try:
                p[field] = json.loads(p[field])
            except Exception:
                p[field] = None
    if isinstance(p.get("raw_notes"), str):
        try:
            p["raw_notes"] = json.loads(p["raw_notes"])
        except Exception:
            p["raw_notes"] = []
    return p


@app.get("/api/patients")
async def list_patients(
    routing_decision: Optional[str] = Query(None),
    facility_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
):
    patients = get_all_patients(routing_decision=routing_decision, facility_id=facility_id)
    patients = [_parse_json_fields(p) for p in patients]

    if search:
        q = search.lower()
        patients = [
            p for p in patients
            if q in (p.get("patient_id") or "").lower()
            or q in (p.get("first_name") or "").lower()
            or q in (p.get("last_name") or "").lower()
            or q in (p.get("wound_type") or "").lower()
        ]

    return patients


@app.get("/api/patients/{patient_id}")
async def get_patient_detail(patient_id: str):
    p = get_patient(patient_id)
    if not p:
        return JSONResponse({"error": "Patient not found"}, status_code=404)
    return _parse_json_fields(p)


@app.get("/api/stats")
async def get_overview_stats():
    stats = get_stats()
    api_health = get_api_health()
    last_sync = get_sync_state("last_sync")

    total = stats.get("total") or 0
    avg_conf = stats.get("avg_confidence") or 0

    return {
        "total_patients": total,
        "auto_accept": stats.get("auto_accept") or 0,
        "flag_for_review": stats.get("flag_for_review") or 0,
        "reject": stats.get("reject") or 0,
        "medicare_b_count": stats.get("medicare_b_count") or 0,
        "avg_confidence_pct": round((avg_conf or 0) * 100, 1),
        "last_sync": last_sync,
        "api_health": {
            "total_requests": api_health.get("total_requests") or 0,
            "total_429s": api_health.get("total_429s") or 0,
            "total_retries": api_health.get("total_retries") or 0,
            "failed_requests": api_health.get("failed_requests") or 0,
            "avg_retry_delay_s": round(api_health.get("avg_retry_delay") or 0, 1),
        }
    }


@app.post("/api/sync")
async def start_sync(
    background_tasks: BackgroundTasks,
    use_llm: bool = Query(True),
):
    if sync_progress["running"]:
        return {"status": "already_running", "progress": sync_progress}

    background_tasks.add_task(run_sync, use_llm=use_llm)
    return {"status": "started", "message": "Sync pipeline started in background"}


@app.get("/api/sync/status")
async def get_sync_status():
    return sync_progress


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ClaimLens AI"}
