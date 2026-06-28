from __future__ import annotations

import re

from billready.extraction.prose import is_prose_note, parse_prose_note
from billready.extraction.text import parse_wound_text
from billready.models import WoundExtraction

MULTI_WOUND_SPLITTERS = re.compile(
    r"(?<=\.)\s+(?=[A-Z])|(?:\.\s*)?(?:also eval|second wound|wound also|additional wound|"
    r"secondarily|other wound)",
    re.IGNORECASE,
)

WOUND_SEGMENT_MARKERS = re.compile(
    r"(?:pressure\s+ulcer|diabetic|venous|arterial|surgical|abscess|burn|wound|heel\s+wound|"
    r"Wound note)",
    re.IGNORECASE,
)


def is_multi_wound_note(text: str) -> bool:
    segments = _split_wound_segments(text)
    wound_segments = [s for s in segments if WOUND_SEGMENT_MARKERS.search(s)]
    return len(wound_segments) >= 2


def _split_wound_segments(text: str) -> list[str]:
    parts = MULTI_WOUND_SPLITTERS.split(text)
    segments = [p.strip() for p in parts if p.strip() and len(p.strip()) > 20]
    if len(segments) <= 1:
        sentences = re.split(r"(?<=\.)\s+", text)
        segments = [s.strip() for s in sentences if WOUND_SEGMENT_MARKERS.search(s)]
    return segments if segments else [text]


def _segment_score(wound: WoundExtraction) -> float:
    score = wound.confidence
    if wound.is_complete():
        score += 10
    if wound.length_cm and wound.width_cm:
        score += wound.length_cm * wound.width_cm
    if wound.depth_cm is not None:
        score += 2
    return score


def parse_multi_wound_note(text: str) -> WoundExtraction:
    segments = _split_wound_segments(text)
    candidates: list[WoundExtraction] = []

    for segment in segments:
        if not WOUND_SEGMENT_MARKERS.search(segment):
            continue
        if is_prose_note(segment):
            parsed = parse_prose_note(segment)
        else:
            parsed = parse_wound_text(segment, source="note_multi", base_confidence=0.65)
        candidates.append(parsed)

    if not candidates:
        return parse_wound_text(text, source="note_text", base_confidence=0.6)

    primary = max(candidates, key=_segment_score)
    primary.source = "note_multi_primary"
    if len(candidates) > 1:
        primary.evidence["multi_wound"] = (
            f"Primary of {len(candidates)} wounds (selected by completeness + size)"
        )
    return primary
