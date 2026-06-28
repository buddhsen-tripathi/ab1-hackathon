from __future__ import annotations

import re

from billready.extraction.text import (
    extract_drainage,
    extract_location,
    extract_measurements,
    extract_stage,
    extract_wound_type,
    normalize_drainage,
)
from billready.models import WoundExtraction

PROSE_MEAS_PATTERN = re.compile(
    r"Meas\.?\s*([\d.]+)\s*[x×]\s*([\d.]+)\s*(?:[x×]\s*([\d.]+))?\s*cm",
    re.IGNORECASE,
)

APRX_MEAS_PATTERN = re.compile(
    r"measures?\s+aprx\.?\s*([\d.]+)\s*[x×]\s*([\d.]+)\s*cm",
    re.IGNORECASE,
)

SEPARATE_DEPTH_PATTERN = re.compile(
    r"(?:,\s*)?depth\s+([\d.]+)\s*cm|([\d.]+)\s*cm\s+deep",
    re.IGNORECASE,
)

INLINE_DIMS_PATTERN = re.compile(
    r"([\d.]+)\s*[x×]\s*([\d.]+)(?:\s*,\s*([\d.]+)\s*cm\s+deep)?",
    re.IGNORECASE,
)

PROSE_DRAINAGE_PATTERN = re.compile(
    r"\b(none|no|min(?:imal)?|light|mod(?:erate)?|heavy|large|copious)\b"
    r"(?:\s+\w+)*\s+drainage|\bdrainage[:\s-]+(\w+)",
    re.IGNORECASE,
)

PROSE_LOCATION_PATTERN = re.compile(
    r"(?:Wound note\s*-\s*|Pressure Ulcer\s+)([A-Za-z\s]+?)(?:\.|,|\s+Meas|\s+measures)",
    re.IGNORECASE,
)


def is_prose_note(text: str) -> bool:
    return bool(
        re.search(r"Meas\.?\s*\d", text, re.IGNORECASE)
        or re.search(r"measures?\s+aprx", text, re.IGNORECASE)
        or re.search(r"Wound note\s*-", text, re.IGNORECASE)
    )


def _extract_prose_measurements(text: str) -> tuple[float | None, float | None, float | None]:
    match = PROSE_MEAS_PATTERN.search(text)
    if match:
        depth = float(match.group(3)) if match.group(3) else None
        if depth is None:
            depth = _extract_separate_depth(text)
        return float(match.group(1)), float(match.group(2)), depth

    aprx = APRX_MEAS_PATTERN.search(text)
    if aprx:
        depth = _extract_separate_depth(text)
        return float(aprx.group(1)), float(aprx.group(2)), depth

    inline = INLINE_DIMS_PATTERN.search(text)
    if inline:
        depth = float(inline.group(3)) if inline.group(3) else _extract_separate_depth(text)
        return float(inline.group(1)), float(inline.group(2)), depth

    return extract_measurements(text)


def _extract_separate_depth(text: str) -> float | None:
    match = SEPARATE_DEPTH_PATTERN.search(text)
    if match:
        return float(match.group(1) or match.group(2))
    return None


def _extract_prose_drainage(text: str) -> str | None:
    match = PROSE_DRAINAGE_PATTERN.search(text)
    if match:
        token = (match.group(1) or match.group(2) or "").lower()
        return normalize_drainage(token)
    return extract_drainage(text)


def _extract_prose_location(text: str) -> str | None:
    match = PROSE_LOCATION_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return extract_location(text)


def parse_prose_note(text: str) -> WoundExtraction:
    wound_type = extract_wound_type(text)
    stage = extract_stage(text)
    location = _extract_prose_location(text)
    length, width, depth = _extract_prose_measurements(text)
    drainage = _extract_prose_drainage(text)

    fields_found = sum(
        1 for v in (wound_type, length, width, depth, drainage) if v is not None
    )
    is_complete = all(v is not None for v in (wound_type, length, width, depth, drainage))
    confidence = 0.9 if is_complete else 0.75 * (fields_found / 5)

    evidence: dict[str, str] = {}
    for field, pattern in [
        ("measurements", PROSE_MEAS_PATTERN),
        ("measurements", APRX_MEAS_PATTERN),
        ("drainage", PROSE_DRAINAGE_PATTERN),
        ("location", PROSE_LOCATION_PATTERN),
    ]:
        m = pattern.search(text)
        if m and field not in evidence:
            evidence[field] = m.group(0)

    return WoundExtraction(
        wound_type=wound_type,
        stage=stage,
        location=location,
        length_cm=length,
        width_cm=width,
        depth_cm=depth,
        drainage_amount=drainage,
        source="note_prose",
        confidence=round(confidence, 2),
        raw_snippet=text[:300],
        evidence=evidence,
    )
