"""Grounded chat agent for the dashboard.

Answers questions about the pipeline and its results by giving the model a
compact, live snapshot of the data (counts, request stats, characterization,
extraction + eligibility summaries) and streaming the reply from OpenRouter.
"""
import json

import httpx

from . import characterize, db
from .config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from .eligibility import store as eligibility_store
from .pcc_client import STATS
from .preprocess import store as preprocess_store

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """\
You are the analyst assistant embedded in the ABI wound-care billing pipeline \
dashboard. You help a non-technical biller and the engineering team understand \
the pipeline and its results.

Domain: Medicare Part B wound-care billing. Each patient is routed to one of \
auto_accept, flag_for_review, or reject. Only patients with active Medicare \
Part B (MCB) coverage are billable.

Rules:
- Answer using the DATA SNAPSHOT below and the conversation. If a detail is not \
in the snapshot, say so plainly instead of inventing numbers.
- Be concise and specific; cite concrete numbers from the snapshot.
- Plain language, short paragraphs. Avoid markdown tables unless asked."""


def _safe(fn, default):
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - snapshot is best-effort
        return {"unavailable": str(exc)[:120]} if default is None else default


def build_context():
    """A trimmed, information-dense snapshot of the current pipeline state."""
    rep = _safe(characterize.report, {})
    notes = rep.get("notes", {}) if isinstance(rep, dict) else {}
    assess = rep.get("assessments", {}) if isinstance(rep, dict) else {}
    cov = rep.get("coverage", {}) if isinstance(rep, dict) else {}

    return {
        "table_counts": _safe(db.list_tables, {}),
        "request_stats": _safe(STATS.snapshot, {}),
        "patients": rep.get("patients") if isinstance(rep, dict) else None,
        "coverage": {
            "patients_with_active_MCB": cov.get("patients_with_active_MCB"),
            "payer_type_distribution": cov.get("payer_type_distribution"),
        },
        "notes_quality": {
            "format_family": notes.get("format_family"),
            "measurement_dims": notes.get("measurement_dims"),
            "drainage_keyword_found": notes.get("drainage_keyword_found"),
            "doubled_word_trap": notes.get("doubled_word_trap"),
        },
        "assessments_quality": {
            "raw_json_shape": assess.get("raw_json_shape"),
            "laterality_conflict_trap": assess.get("laterality_conflict_trap"),
        },
        "extraction_summary": _safe(preprocess_store.summary, {}),
        "eligibility_summary": _safe(eligibility_store.summary, {}),
    }


def stream_chat(messages):
    """Yield reply text deltas for a list of {role, content} messages."""
    if not OPENROUTER_API_KEY:
        yield "The chat agent is not configured (missing OPENROUTER_API_KEY)."
        return

    snapshot = build_context()
    system = (
        SYSTEM_PROMPT
        + "\n\nDATA SNAPSHOT (JSON):\n"
        + json.dumps(snapshot, default=str)
    )
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "system", "content": system}, *messages],
        "stream": True,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "ABI Wound-Care Pipeline",
    }

    with httpx.stream(
        "POST", OPENROUTER_URL, json=payload, headers=headers, timeout=120
    ) as resp:
        if resp.status_code != 200:
            body = resp.read().decode("utf-8", "ignore")[:300]
            yield f"[chat error {resp.status_code}: {body}]"
            return
        for line in resp.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                delta = obj["choices"][0]["delta"].get("content")
            except Exception:
                continue
            if delta:
                yield delta
