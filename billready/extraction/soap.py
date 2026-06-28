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


def is_soap_note(text: str) -> bool:
    return bool(
        re.search(r"Location:\s", text, re.IGNORECASE)
        and re.search(r"(Length:|Wound Type:)", text, re.IGNORECASE)
    )


def parse_soap_note(text: str) -> WoundExtraction:
    """Parse structured SOAP / SPN notes with labeled fields."""
    wound_type_raw = re.search(r"Wound Type:\s*([^\n]+)", text, re.IGNORECASE)
    wound_type = None
    stage = None
    if wound_type_raw:
        wt_line = wound_type_raw.group(1).strip()
        wound_type = extract_wound_type(wt_line) or wt_line.split(",")[0].strip().lower()
        stage = extract_stage(wt_line)

    if not stage:
        stage = extract_stage(text)

    location = extract_location(text)
    length, width, depth = extract_measurements(text)

    drainage_raw = re.search(r"Drainage:\s*([^\n]+)", text, re.IGNORECASE)
    drainage = normalize_drainage(drainage_raw.group(1)) if drainage_raw else extract_drainage(text)

    if not wound_type:
        wound_type = extract_wound_type(text)

    fields_found = sum(
        1
        for v in (wound_type, length, width, depth, drainage)
        if v is not None
    )
    confidence = 0.95 if fields_found >= 4 else 0.75 * (fields_found / 5)

    return WoundExtraction(
        wound_type=wound_type,
        stage=stage,
        location=location,
        length_cm=length,
        width_cm=width,
        depth_cm=depth,
        drainage_amount=drainage,
        source="note_soap",
        confidence=round(confidence, 2),
        raw_snippet=text[:300],
    )
