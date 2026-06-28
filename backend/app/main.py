"""FastAPI server for the wound-care billing pipeline.

Endpoints:
  GET /health            liveness
  GET /stats             request stats + data characterization
  GET /patients          ingested patient roster (optionally by facility)
  POST /ingest           trigger a fresh data pull (runs in background)
"""
import json
import traceback

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import agent, characterize, db, ingest, llm
from .eligibility import run as eligibility_run
from .eligibility import store as eligibility_store
from .preprocess import run as preprocess_run
from .preprocess import store as preprocess_store
from .pcc_client import STATS

app = FastAPI(title="ABI Wound-Care Billing Pipeline", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats():
    return {"request_stats": STATS.snapshot(), "data": characterize.report()}


@app.get("/patients")
def patients(facility_id: int | None = Query(default=None)):
    return db.fetch_patients(facility_id)


@app.get("/db/tables")
def db_tables():
    """Row counts per stored table (drives the table picker)."""
    return db.list_tables()


@app.get("/db/table/{name}")
def db_table(
    name: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    facility_id: int | None = Query(default=None),
):
    """Paginated rows of a stored table's original records, optionally filtered."""
    try:
        return db.fetch_table(
            name, limit=limit, offset=offset, search=search, facility_id=facility_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/ingest")
def trigger_ingest(background_tasks: BackgroundTasks):
    background_tasks.add_task(ingest.run)
    return {"status": "ingestion started"}


@app.get("/extractions/summary")
def extractions_summary():
    """Preprocessing output: field coverage, billing-ready %, traps, format mix."""
    return preprocess_store.summary()


@app.get("/llm/observability")
def llm_observability():
    """LLM layer observability: config + live call stats, the cascade's
    selectivity from the last extract run, and the persisted method mix."""
    s = preprocess_store.summary()
    return {
        "config": llm.info(),
        "cascade": preprocess_run.LAST_CASCADE,
        "method_distribution": s.get("method_distribution", {}),
        "avg_confidence": s.get("avg_confidence", 0),
        "total_wound_rows": s.get("total_wound_rows", 0),
    }


@app.post("/preprocess")
def trigger_preprocess(background_tasks: BackgroundTasks):
    """Re-run extraction over the ingested notes + assessments."""
    background_tasks.add_task(preprocess_run.run)
    return {"status": "preprocess started"}


@app.get("/eligibility")
def eligibility(
    decision: str | None = Query(default=None),
    facility_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    eligible: bool | None = Query(default=None),
    new_admission: bool | None = Query(default=None),
    missing: str | None = Query(default=None),
):
    """Biller-facing routing worklist (auto_accept / flag_for_review / reject)."""
    return eligibility_store.fetch_results(
        decision=decision, facility_id=facility_id, search=search,
        eligible=eligible, new_admission=new_admission, missing=missing,
    )


@app.get("/eligibility/summary")
def eligibility_summary():
    return eligibility_store.summary()


@app.get("/eligibility/{patient_id}")
def eligibility_detail(patient_id: str):
    """One patient's decision + the wound extractions behind it (evidence)."""
    detail = eligibility_store.fetch_detail(patient_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"unknown patient: {patient_id}")
    return detail


@app.post("/route")
def trigger_route(background_tasks: BackgroundTasks):
    """Re-run reconciliation + routing over the current wound_extractions."""
    background_tasks.add_task(eligibility_run.run)
    return {"status": "routing started"}


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    messages: list[ChatTurn]


@app.post("/chat")
def chat(body: ChatBody):
    """Agentic assistant grounded in a live snapshot of the pipeline data.

    Streams the reply as plain text so the UI can render tokens as they arrive.
    """
    msgs = [{"role": m.role, "content": m.content} for m in body.messages][-12:]

    def gen():
        try:
            for delta in agent.stream_chat(msgs):
                yield delta
        except Exception as exc:
            yield f"\n[error: {exc}]"

    return StreamingResponse(
        gen(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/pipeline/stream")
def pipeline_stream():
    """Run the full pipeline and stream each stage event as Server-Sent Events.

    The frontend opens an EventSource on this endpoint and visualizes progress
    (roster, records with live 429 retries, store, characterize) as it happens.
    """

    def event_source():
        try:
            for ev in ingest.run_stream():
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as exc:  # surface failures to the UI instead of hanging
            err = {
                "type": "error",
                "message": str(exc),
                "trace": traceback.format_exc()[-800:],
            }
            yield f"data: {json.dumps(err)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
