from __future__ import annotations

import html
import re

from billready.models import WoundExtraction

HIGHLIGHT_STYLE = (
    "background-color: #fef08a; padding: 1px 3px; border-radius: 3px; font-weight: 600;"
)


def build_evidence_html(note_text: str, wound: WoundExtraction | None) -> str:
    """Return note text with extracted spans highlighted for the UI."""
    if not note_text:
        return "<em>No note text available.</em>"
    if not wound or not wound.evidence:
        return f"<pre style='white-space: pre-wrap;'>{html.escape(note_text)}</pre>"

    spans: list[tuple[int, int, str]] = []
    for field, snippet in wound.evidence.items():
        if field == "multi_wound":
            continue
        start = note_text.find(snippet)
        if start >= 0:
            spans.append((start, start + len(snippet), field))

    if not spans:
        return _highlight_by_patterns(note_text, wound)

    spans.sort(key=lambda s: s[0])
    merged = _merge_spans(spans)

    parts: list[str] = []
    cursor = 0
    for start, end, field in merged:
        if start > cursor:
            parts.append(html.escape(note_text[cursor:start]))
        parts.append(
            f"<mark style='{HIGHLIGHT_STYLE}' title='{html.escape(field)}'>"
            f"{html.escape(note_text[start:end])}</mark>"
        )
        cursor = end
    if cursor < len(note_text):
        parts.append(html.escape(note_text[cursor:]))

    return f"<pre style='white-space: pre-wrap; font-family: inherit;'>{''.join(parts)}</pre>"


def _merge_spans(spans: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    if not spans:
        return []
    merged = [spans[0]]
    for start, end, field in spans[1:]:
        prev_start, prev_end, prev_field = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end), f"{prev_field},{field}")
        else:
            merged.append((start, end, field))
    return merged


def _highlight_by_patterns(note_text: str, wound: WoundExtraction) -> str:
    patterns: list[str] = []
    if wound.wound_type:
        patterns.append(re.escape(wound.wound_type))
    if wound.location:
        patterns.append(re.escape(wound.location))
    if wound.length_cm and wound.width_cm:
        patterns.append(rf"{wound.length_cm}\s*[x×]\s*{wound.width_cm}")

    escaped = html.escape(note_text)
    for pattern in patterns:
        escaped = re.sub(
            f"({pattern})",
            rf"<mark style='{HIGHLIGHT_STYLE}'>\1</mark>",
            escaped,
            flags=re.IGNORECASE,
        )
    return f"<pre style='white-space: pre-wrap; font-family: inherit;'>{escaped}</pre>"


def collect_evidence_from_text(text: str, wound: WoundExtraction) -> WoundExtraction:
    """Populate evidence dict by locating extracted values in source text."""
    evidence = dict(wound.evidence)
    checks = [
        ("wound_type", wound.wound_type),
        ("location", wound.location),
        ("stage", f"stage {wound.stage}" if wound.stage else None),
        ("drainage", wound.drainage_amount),
    ]
    if wound.length_cm and wound.width_cm:
        dim_pattern = rf"{wound.length_cm}\s*[x×]\s*{wound.width_cm}"
        match = re.search(dim_pattern, text, re.IGNORECASE)
        if match:
            evidence["measurements"] = match.group(0)

    for field, value in checks:
        if not value or field in evidence:
            continue
        idx = text.lower().find(str(value).lower())
        if idx >= 0:
            evidence[field] = text[idx : idx + len(str(value))]

    wound.evidence = evidence
    return wound
