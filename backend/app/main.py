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

from . import characterize, db, ingest
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
):
    """Paginated rows of a stored table's original records."""
    try:
        return db.fetch_table(name, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/ingest")
def trigger_ingest(background_tasks: BackgroundTasks):
    background_tasks.add_task(ingest.run)
    return {"status": "ingestion started"}


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
