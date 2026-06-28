from __future__ import annotations

import json
import logging
from collections.abc import Callable

from billready.config import LLM_CHUNK_SIZE, LLM_MODEL, openai_api_key
from billready.models import EligibilityResult, PatientRecord

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str, int, int], None]


def _get_note_text(record: PatientRecord) -> str:
    if not record.notes:
        return ""
    return record.notes[0].get("note_text") or ""


def _build_batch_prompt(cases: list[tuple[EligibilityResult, str]]) -> str:
    blocks: list[str] = []
    for result, note_text in cases:
        missing = ", ".join(result.missing_fields) or "none"
        blocks.append(
            f"""--- {result.patient_id} ---
Missing / flagged fields: {missing}
Rules reason: {result.reason[:220]}
Extracted so far: type={result.wound_type}, stage={result.stage}, location={result.location}, """
            f"""L={result.length_cm}cm W={result.width_cm}cm D={result.depth_cm}cm, drainage={result.drainage_amount}
Note excerpt:
\"\"\"{note_text[:900]}\"\"\""""
        )

    patient_ids = [r.patient_id for r, _ in cases]
    return f"""You help wound care billers triage ambiguous Medicare Part B cases.

These {len(cases)} patients were flagged NEEDS REVIEW by a rules pipeline (missing or unclear documentation).
For EACH patient, read the note and give a short, practical suggestion for the biller.
Do NOT change routing — advisory only. Be conservative.

{chr(10).join(blocks)}

Reply JSON only with one entry per patient_id ({", ".join(patient_ids)}):
{{"reviews": [{{"patient_id": "...", "suggestion": "one sentence: what to do next", "verdict": "billable|needs_documentation|unclear"}}]}}"""


def _chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _mark_skipped(results: list[EligibilityResult], note: str) -> None:
    for result in results:
        if result.routing_decision == "flag_for_review":
            result.llm_check = "skipped"
            result.llm_check_note = note


def suggest_for_review(
    results: list[EligibilityResult],
    records_by_id: dict[str, PatientRecord],
    *,
    model: str = LLM_MODEL,
    chunk_size: int = LLM_CHUNK_SIZE,
    on_progress: ProgressFn | None = None,
) -> tuple[list[EligibilityResult], dict[str, int]]:
    """
    LLM copilot for flag_for_review cases only. Adds advisory suggestions; never changes routing.
    Returns (updated_results, stats) with calls, suggestions, skipped.
    """
    stats = {"calls": 0, "suggestions": 0, "skipped": 0}

    review_cases = [r for r in results if r.routing_decision == "flag_for_review"]
    if not review_cases:
        return results, stats

    api_key = openai_api_key()
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — skipping LLM suggestions")
        _mark_skipped(review_cases, "No API key configured")
        stats["skipped"] = len(review_cases)
        return results, stats

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed — run: pip install openai")
        _mark_skipped(review_cases, "openai package not installed")
        stats["skipped"] = len(review_cases)
        return results, stats

    client = OpenAI(api_key=api_key)
    cases: list[tuple[EligibilityResult, str]] = []
    for result in review_cases:
        record = records_by_id.get(result.patient_id)
        note_text = _get_note_text(record) if record else ""
        cases.append((result, note_text))

    batches = _chunked(cases, chunk_size)
    total_batches = len(batches)

    for batch_idx, batch in enumerate(batches, start=1):
        if on_progress:
            on_progress(
                f"LLM suggestions batch {batch_idx}/{total_batches} ({len(batch)} patients)…",
                batch_idx - 1,
                total_batches,
            )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You advise clinical billers on wound care documentation gaps. "
                            "Reply JSON only with a reviews array covering every patient_id."
                        ),
                    },
                    {"role": "user", "content": _build_batch_prompt(batch)},
                ],
                temperature=0,
                max_tokens=min(500 + 150 * len(batch), 4000),
                response_format={"type": "json_object"},
            )
            stats["calls"] += 1
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)
            reviews = parsed.get("reviews") or []
            by_id = {
                str(item.get("patient_id", "")): item
                for item in reviews
                if isinstance(item, dict)
            }

            for result, _ in batch:
                item = by_id.get(result.patient_id)
                if not item:
                    result.llm_check = "skipped"
                    result.llm_check_note = "Missing from LLM batch response"
                    stats["skipped"] += 1
                    continue

                suggestion = str(item.get("suggestion", "")).strip()
                verdict = str(item.get("verdict", "unclear")).strip().lower()
                if verdict not in ("billable", "needs_documentation", "unclear"):
                    verdict = "unclear"

                result.llm_check = verdict
                result.llm_check_note = suggestion or "No suggestion returned"
                stats["suggestions"] += 1

        except Exception as exc:
            logger.warning("LLM batch %d failed: %s", batch_idx, exc)
            for result, _ in batch:
                result.llm_check = "skipped"
                result.llm_check_note = f"Batch error: {exc}"
                stats["skipped"] += 1

    if on_progress:
        on_progress(
            f"LLM suggestions complete — {stats['suggestions']} patients",
            total_batches,
            total_batches,
        )

    logger.info(
        "LLM suggestions: %d API calls, %d suggestions, %d skipped",
        stats["calls"],
        stats["suggestions"],
        stats["skipped"],
    )
    return results, stats
