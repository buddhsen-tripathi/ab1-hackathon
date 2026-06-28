"""Ingestion pipeline: pull all patients + their diagnoses, coverage, notes,
and assessments.

Parallelism unit is the *individual call*, not the patient bundle — all
~1,200 child requests go into one worker pool together, so a 429-sleep on
one call never blocks the three sibling calls behind it (no intra-bundle
head-of-line blocking). Retries run aggressively (honor_retry_after=False):
the 429 is random, not a congestion signal, so near-immediate retry is valid
and collapses the sleep tail to ~0.
"""
import concurrent.futures as cf
import time
from collections import Counter

from . import db, characterize
from .pcc_client import get, STATS

FACILITIES = [101, 102, 103]
# 48 is the sweet spot: ~1.5x faster than 12, before returns go sublinear
# against the server's RTT floor. The 429 rate is random per-request (~0.30 at
# every concurrency level), so higher fan-out carries no rate-limit penalty.
MAX_WORKERS = 48

# kind -> (endpoint, which patient identifier it keys on)
ENDPOINTS = {
    "diagnoses": ("/pcc/diagnoses", "patient_id"),  # FA-001 (string)
    "coverage": ("/pcc/coverage", "patient_id"),    # FA-001 (string)
    "notes": ("/pcc/notes", "id"),                  # 1 (integer)
    "assessments": ("/pcc/assessments", "id"),      # 1 (integer)
}


def fetch_one(kind, key, honor_retry_after):
    """Runs on a worker thread. One endpoint, one patient -> list of rows."""
    path, _ = ENDPOINTS[kind]
    return get(path, {"patient_id": key}, honor_retry_after=honor_retry_after)


def run_stream(honor_retry_after=False, max_workers=MAX_WORKERS):
    """Run the full pipeline as a generator of structured progress events.

    Each yielded dict is a self-describing event (type + payload) that the API
    layer serializes to Server-Sent Events so the UI can visualize the run live.
    The fan-out still happens on a thread pool; this generator runs on the main
    thread and yields as futures complete, so events stream in real time.
    """
    t0 = time.time()
    STATS.reset()
    db.init()
    conn = db.connect()
    yield {
        "type": "pipeline_start",
        "ts": t0,
        "facilities": FACILITIES,
        "max_workers": max_workers,
    }

    # ---- Stage: roster ----
    yield {"type": "stage_start", "stage": "roster",
           "message": f"Fetching patient rosters for {len(FACILITIES)} facilities"}
    patients = []
    for fid in FACILITIES:
        rows = get("/pcc/patients", {"facility_id": fid},
                   honor_retry_after=honor_retry_after)
        patients.extend(rows)
        yield {"type": "roster", "facility": fid, "count": len(rows),
               "running_total": len(patients), "stats": STATS.snapshot()}
    db.upsert_patients(conn, patients)
    yield {"type": "stage_complete", "stage": "roster",
           "total_patients": len(patients), "stats": STATS.snapshot()}

    # ---- Stage: records (one task per endpoint x patient) ----
    tasks = []
    for p in patients:
        for kind, (_, id_field) in ENDPOINTS.items():
            tasks.append((kind, p[id_field]))
    total = len(tasks)
    yield {"type": "stage_start", "stage": "records", "total": total,
           "message": f"Fetching {total} child records ({max_workers} workers)"}

    results = {kind: [] for kind in ENDPOINTS}
    by_kind = Counter()
    done = 0
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_to_task = {
            ex.submit(fetch_one, kind, key, honor_retry_after): kind
            for kind, key in tasks
        }
        for fut in cf.as_completed(fut_to_task):
            kind = fut_to_task[fut]
            results[kind].extend(fut.result())
            by_kind[kind] += 1
            done += 1
            if done % 20 == 0 or done == total:
                yield {"type": "progress", "stage": "records",
                       "done": done, "total": total,
                       "by_kind": dict(by_kind), "stats": STATS.snapshot()}
    yield {"type": "stage_complete", "stage": "records", "done": done,
           "by_kind": dict(by_kind), "stats": STATS.snapshot()}

    # ---- Stage: store (single bulk write, SQLite conn stays single-threaded) ----
    yield {"type": "stage_start", "stage": "store",
           "message": "Bulk writing records to SQLite"}
    db.upsert_bundle(
        conn, results["diagnoses"], results["coverage"],
        results["notes"], results["assessments"],
    )
    counts = db.counts(conn)
    yield {"type": "stage_complete", "stage": "store", "counts": counts}

    # ---- Stage: characterize ----
    yield {"type": "stage_start", "stage": "characterize",
           "message": "Profiling formats, payer signal and dirty-data traps"}
    rep = characterize.report()
    yield {"type": "stage_complete", "stage": "characterize"}

    elapsed = round(time.time() - t0, 1)
    conn.close()
    yield {"type": "pipeline_complete", "elapsed_sec": elapsed,
           "counts": counts, "stats": STATS.snapshot(), "data": rep}


def run(honor_retry_after=False, max_workers=MAX_WORKERS):
    """Run the pipeline to completion, printing a trace. Returns the final event."""
    last = None
    for ev in run_stream(honor_retry_after, max_workers):
        last = ev
        if ev["type"] in ("stage_start", "stage_complete", "pipeline_complete"):
            print(ev["type"], ev.get("stage", ""), ev.get("message", ""))
    return last


if __name__ == "__main__":
    run()
