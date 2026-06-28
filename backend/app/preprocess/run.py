"""Orchestrate preprocessing: read raw notes + assessments from Postgres,
parse each into canonical wound rows, write the wound_extractions table,
print a coverage/quality summary.

Run: python -m app.preprocess.run
"""
import json
import time

from ..db import connect
from . import parsers, store


def _load_documents():
    docs = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, patient_id, note_type, note_text FROM notes")
        for r in cur.fetchall():
            docs.append({"kind": "note", **r})
        cur.execute("SELECT id, patient_id, assessment_type, raw_json FROM assessments")
        for r in cur.fetchall():
            docs.append({"kind": "assessment", **r})
    return docs


def run():
    t0 = time.time()
    store.init()
    docs = _load_documents()
    print(f"Loaded {len(docs)} source documents")

    rows = []
    errors = 0
    for doc in docs:
        try:
            for ext in parsers.parse_document(doc):
                rows.append(ext.as_row())
        except Exception as exc:  # never let one bad doc kill the batch
            errors += 1
            print(f"  ! parse error doc {doc.get('kind')}:{doc.get('id')} -> {exc}")

    store.replace_all(rows)
    elapsed = time.time() - t0

    print("\n=== PREPROCESS COMPLETE ===")
    print(f"  wall time: {elapsed:.1f}s | parse errors: {errors}")
    print(json.dumps(store.summary(), indent=2))


if __name__ == "__main__":
    run()
