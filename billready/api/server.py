from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from billready.api.pipeline_job import pipeline_jobs
from billready.config import BASE_URL, LLM_CHUNK_SIZE, LLM_MODEL, llm_available, llm_unavailable_reason
from billready.eligibility.routing import ALL_WOUND_FIELDS, FIELD_LABELS
from billready.extraction.evidence import build_evidence_html
from billready.extraction.fusion import extract_patient_wound
from billready.models import PatientRecord
from billready.storage.cache import CacheStore

FACILITY_NAMES = {101: "Facility A", 102: "Facility B", 103: "Facility C"}

app = FastAPI(title="BillReady API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

cache = CacheStore()


def _normalize_row(row: dict) -> dict:
    """Ensure consistent types for JSON serialization."""
    out = dict(row)
    for key in ("has_active_mcb", "is_new_admission", "submission_eligible"):
        if key in out:
            out[key] = out[key] in (True, "True", 1, "1")
    if "missing_fields" not in out or out["missing_fields"] is None:
        out["missing_fields"] = []
    elif isinstance(out["missing_fields"], str):
        out["missing_fields"] = [f for f in out["missing_fields"].split(",") if f]
    for key in ("length_cm", "width_cm", "depth_cm", "extraction_confidence"):
        if out.get(key) is not None and out[key] != "":
            try:
                out[key] = float(out[key])
            except (TypeError, ValueError):
                pass
    if out.get("facility_id") is not None:
        out["facility_id"] = int(out["facility_id"])
    if out.get("internal_id") is not None:
        out["internal_id"] = int(out["internal_id"])
    return out


def _load_all() -> list[dict]:
    return [_normalize_row(r) for r in cache.load_eligibility_results()]


def _matches(row: dict, params: dict[str, Any]) -> bool:
    if params.get("facility_id") and row["facility_id"] != params["facility_id"]:
        return False
    if params.get("routing_decision") and row["routing_decision"] not in params["routing_decision"]:
        return False
    if params.get("submission_eligible") is not None:
        eligible = row.get("submission_eligible") or row.get("has_active_mcb")
        if bool(eligible) != params["submission_eligible"]:
            return False
    if params.get("new_admission") and not row.get("is_new_admission"):
        return False
    if params.get("search"):
        q = params["search"].lower()
        hay = " ".join(
            str(row.get(k, "") or "")
            for k in ("patient_id", "first_name", "last_name")
        ).lower()
        if q not in hay:
            return False
    missing_filter = params.get("missing_fields") or []
    if missing_filter:
        row_missing = set(row.get("missing_fields") or [])
        if not row_missing.intersection(missing_filter):
            return False
    return True


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


class PipelineRunRequest(BaseModel):
    clear_cache: bool = False
    llm_verify: bool = False
    use_cache: bool = True


@app.get("/api/config")
def config() -> dict:
    reason = llm_unavailable_reason()
    return {
        "pcc_api_url": BASE_URL,
        "llm_available": llm_available(),
        "llm_unavailable_reason": reason,
        "llm_model": LLM_MODEL,
        "llm_chunk_size": LLM_CHUNK_SIZE,
        "openai_setup": "Create .env in project root with OPENAI_API_KEY=sk-... (see .env.example)",
    }


@app.get("/api/pipeline/status")
def pipeline_status() -> dict:
    return pipeline_jobs.get_status()


@app.post("/api/pipeline/run")
def pipeline_run(body: PipelineRunRequest) -> dict:
    if body.llm_verify and not llm_available():
        raise HTTPException(
            400,
            "OPENAI_API_KEY not configured. Add it to .env — see .env.example",
        )
    try:
        return pipeline_jobs.start(
            clear_cache=body.clear_cache,
            llm_verify=body.llm_verify,
            use_cache=body.use_cache,
        )
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/meta")
def meta() -> dict:
    stats = cache.get_cache_stats()
    return {
        "facilities": [{"id": k, "name": v} for k, v in FACILITY_NAMES.items()],
        "field_labels": FIELD_LABELS,
        "wound_fields": ALL_WOUND_FIELDS,
        "routing_labels": {
            "auto_accept": "Ready to Bill",
            "flag_for_review": "Needs Review",
            "reject": "Do Not Route",
        },
        "pipeline": stats.get("last_pipeline_run"),
        "last_sync": stats.get("last_full_sync"),
    }


@app.get("/api/stats")
def stats(
    facility_id: int | None = None,
    submission_eligible: bool | None = None,
    routing_decision: list[str] | None = Query(None),
    missing_fields: list[str] | None = Query(None),
    new_admission: bool | None = None,
    search: str | None = None,
) -> dict:
    params = {
        "facility_id": facility_id,
        "submission_eligible": submission_eligible,
        "routing_decision": routing_decision,
        "missing_fields": missing_fields,
        "new_admission": new_admission,
        "search": search,
    }
    rows = [r for r in _load_all() if _matches(r, params)]
    all_rows = _load_all()

    routing_counts = {"auto_accept": 0, "flag_for_review": 0, "reject": 0}
    missing_counts: dict[str, int] = {f: 0 for f in ALL_WOUND_FIELDS}
    missing_counts["medicare_part_b"] = 0
    missing_counts["wound_documentation"] = 0

    for r in rows:
        routing_counts[r["routing_decision"]] = routing_counts.get(r["routing_decision"], 0) + 1
        for f in r.get("missing_fields") or []:
            missing_counts[f] = missing_counts.get(f, 0) + 1

    return {
        "total": len(all_rows),
        "filtered": len(rows),
        "submission_eligible": sum(1 for r in rows if r.get("submission_eligible")),
        "routing": routing_counts,
        "missing_field_counts": missing_counts,
        "llm_suggestions": sum(
            1
            for r in rows
            if r.get("llm_check") in ("billable", "needs_documentation", "unclear")
        ),
    }


@app.get("/api/patients")
def list_patients(
    facility_id: int | None = None,
    submission_eligible: bool | None = None,
    routing_decision: list[str] | None = Query(None),
    missing_fields: list[str] | None = Query(None),
    new_admission: bool | None = None,
    search: str | None = None,
) -> list[dict]:
    params = {
        "facility_id": facility_id,
        "submission_eligible": submission_eligible,
        "routing_decision": routing_decision,
        "missing_fields": missing_fields,
        "new_admission": new_admission,
        "search": search,
    }
    rows = [r for r in _load_all() if _matches(r, params)]
    for r in rows:
        r["facility_name"] = FACILITY_NAMES.get(r["facility_id"], str(r["facility_id"]))
    return rows


@app.get("/api/patients/{patient_id}")
def patient_detail(patient_id: str) -> dict:
    rows = _load_all()
    row = next((r for r in rows if r["patient_id"] == patient_id), None)
    if not row:
        raise HTTPException(404, "Patient not found")

    internal_id = int(row["internal_id"])
    notes = cache.get_patient_notes(internal_id)
    assessments = cache.get_patient_assessments(internal_id)
    coverage = cache.get_patient_coverage(patient_id)
    diagnoses = cache.get_patient_diagnoses(patient_id)

    record = PatientRecord(
        internal_id=internal_id,
        patient_id=patient_id,
        facility_id=int(row["facility_id"]),
        first_name=row.get("first_name"),
        last_name=row.get("last_name"),
        primary_payer_code=None,
        is_new_admission=bool(row.get("is_new_admission")),
        diagnoses=diagnoses,
        coverage=coverage,
        notes=notes,
        assessments=assessments,
    )
    wound = extract_patient_wound(record)
    note_text = notes[0].get("note_text", "") if notes else ""

    return {
        **row,
        "facility_name": FACILITY_NAMES.get(int(row["facility_id"]), ""),
        "notes": notes,
        "assessments": assessments,
        "coverage": coverage,
        "diagnoses": diagnoses,
        "note_html": build_evidence_html(note_text, wound) if note_text else None,
        "note_text": note_text,
    }
