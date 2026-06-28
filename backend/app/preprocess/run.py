"""Orchestrate preprocessing with the knowledge-base cascade.

Per document:
  1. signature → KB extraction cache  (identical text → skip everything)
  2. heuristic parse (regex/structured) → WoundExtraction(s), already
     KB-normalized (abbreviation expansion + learned synonyms)
  3. confidence gate → escalate hard/low-confidence/conflicted docs to the LLM
     layer, which resolves fields AND teaches the KB new abbreviations/synonyms
  4. cache the result

At the end: roll up per-format patterns, flush everything learned/cached in one
batch, and write the wound_extractions table. One Neon connection for the whole
run (connecting is slow), reused everywhere.

Run: python -m app.preprocess.run
"""
import concurrent.futures as cf
import json
import os
import time

from .. import kb, llm
from ..db import connect
from . import parsers, store

# Escalations are independent network calls — fan them out instead of blocking
# the parse loop one at a time. Tune via LLM_WORKERS (watch provider rate limits).
LLM_WORKERS = int(os.environ.get("LLM_WORKERS", "16"))


def _load_documents(conn):
    docs = []
    with conn.cursor() as cur:
        cur.execute("SELECT id, patient_id, note_type, note_text FROM notes")
        for r in cur.fetchall():
            docs.append({"kind": "note", **r})
        cur.execute("SELECT id, patient_id, assessment_type, raw_json FROM assessments")
        for r in cur.fetchall():
            docs.append({"kind": "assessment", **r})
    return docs


def _doc_text(doc):
    return doc.get("note_text") or doc.get("raw_json") or ""


# Last cascade stat, surfaced by the LLM observability endpoint between runs.
LAST_CASCADE = {}


def run_stream():
    """Generator form of the extract stage: yields stage_start / progress /
    stage_complete events so the live pipeline can visualize it (and the LLM
    cascade's selectivity) in real time."""
    global LAST_CASCADE

    # --- Phase 1: read inputs + load KB (short-lived connection) ----------
    # The Neon link is slow/flaky, so we never hold a connection open across
    # the in-memory parse loop — an idle pooled connection gets dropped.
    with connect() as conn:
        store.init(conn)
        kb.init(conn)
        kb.seed(conn)
        kb.load(conn)
        docs = _load_documents(conn)
    total = len(docs)
    yield {"type": "stage_start", "stage": "extract", "total": total,
           "message": f"Extracting wound fields from {total} documents"}

    # --- Phase 2a: parse in memory; collect the hard docs for escalation ---
    # The parse + cache lookups are fast and stay serial; the slow part — the
    # LLM escalation calls — is deferred so we can fan it out below.
    rows = []
    stat = {"cache_hits": 0, "parsed": 0, "escalated": 0,
            "llm_enriched": 0, "errors": 0}

    def _finalize(sig, exts):
        primary = next((e for e in exts if e.is_primary), exts[0] if exts else None)
        row_dicts = [e.as_row() for e in exts]
        conf = primary.confidence if primary else 0.0
        method = primary.method if primary else "regex"
        kb.cache_put(sig, row_dicts, method, conf)
        rows.extend(row_dicts)

    pending = []  # docs that need an LLM call: {doc, exts, primary, sig}
    for i, doc in enumerate(docs, 1):
        try:
            sig = kb.signature(_doc_text(doc))
            cached = kb.cache_get(sig)
            if cached is not None:                      # 1. memoization
                stat["cache_hits"] += 1
                rows.extend(kb.restamp(cached, doc))
            else:
                exts = parsers.parse_document(doc)      # 2. heuristic parse
                stat["parsed"] += 1
                primary = next((e for e in exts if e.is_primary),
                               exts[0] if exts else None)
                if primary and llm.needs_escalation(doc, primary):  # 3. gate
                    stat["escalated"] += 1
                    pending.append({"doc": doc, "exts": exts, "primary": primary, "sig": sig})
                else:
                    _finalize(sig, exts)                # 4. memoize now
        except Exception:                               # one bad doc never kills the batch
            stat["errors"] += 1
        if i % 40 == 0 or i == total:
            yield {"type": "progress", "stage": "extract", "done": i,
                   "total": total, "cascade": dict(stat)}

    # --- Phase 2b: escalate the hard docs CONCURRENTLY ---------------------
    # Only the network call (llm.escalate) runs on worker threads; applying the
    # enrichment + KB writes stay on this thread, so no locking is needed.
    if pending:
        yield {"type": "progress", "stage": "extract", "done": total, "total": total,
               "cascade": dict(stat),
               "message": f"Escalating {len(pending)} docs to the LLM ({LLM_WORKERS} workers)"}
        done_esc = 0
        with cf.ThreadPoolExecutor(max_workers=LLM_WORKERS) as ex:
            fut_to_item = {
                ex.submit(llm.escalate, it["doc"], it["primary"].as_row()): it
                for it in pending
            }
            for fut in cf.as_completed(fut_to_item):
                it = fut_to_item[fut]
                try:
                    enrich = fut.result()
                except Exception:
                    enrich = None
                if enrich:
                    stat["llm_enriched"] += 1
                    _apply_enrichment(it["exts"], enrich)
                    kb.learn_from(enrich)               # teach the KB
                _finalize(it["sig"], it["exts"])
                done_esc += 1
                if done_esc % 5 == 0 or done_esc == len(pending):
                    yield {"type": "progress", "stage": "extract", "done": total,
                           "total": total, "cascade": dict(stat),
                           "message": f"LLM escalations {done_esc}/{len(pending)}"}

    # --- Phase 3: persist (fresh connection, used immediately) ------------
    with connect() as conn:
        store.replace_all(rows, conn)               # critical output first
        kb.record_patterns(rows, conn)
        kb.flush(conn)
        store_summary = store.summary(conn)

    stat["total"] = total
    LAST_CASCADE = dict(stat)
    yield {"type": "stage_complete", "stage": "extract", "cascade": dict(stat),
           "summary": store_summary, "llm": llm.info()}


def run():
    """Run the extract stage to completion, printing a trace."""
    last = None
    for ev in run_stream():
        last = ev
    if last:
        print("=== PREPROCESS COMPLETE ===")
        print("  cascade:", json.dumps(last.get("cascade", {})))
        print(json.dumps(last.get("summary", {}), indent=2))
    return last


def _apply_enrichment(exts, enrich):
    """Fill gaps on the primary extraction from the LLM's resolved fields,
    bump confidence, and mark the method. Heuristic values win unless null."""
    fields = (enrich or {}).get("fields") or {}
    primary = next((e for e in exts if e.is_primary), exts[0] if exts else None)
    if primary is None:
        return
    for key, val in fields.items():
        if val is not None and getattr(primary, key, None) is None:
            setattr(primary, key, val)
    primary.method = "llm"
    primary.confidence = max(primary.confidence, (enrich or {}).get("confidence", 0.0))
    primary.finalize()


if __name__ == "__main__":
    run()
