from __future__ import annotations

from billready.extraction.assessment import parse_assessment
from billready.extraction.evidence import collect_evidence_from_text
from billready.extraction.multi_wound import is_multi_wound_note, parse_multi_wound_note
from billready.extraction.prose import is_prose_note, parse_prose_note
from billready.extraction.soap import is_soap_note, parse_soap_note
from billready.extraction.text import parse_wound_text
from billready.models import PatientRecord, WoundExtraction


def _pick_best(candidates: list[WoundExtraction]) -> WoundExtraction | None:
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda w: (w.is_complete(), w.confidence, w.length_cm is not None),
    )


def _merge(a: WoundExtraction, b: WoundExtraction) -> WoundExtraction:
    primary, secondary = (a, b) if a.confidence >= b.confidence else (b, a)
    evidence = {**secondary.evidence, **primary.evidence}
    return WoundExtraction(
        wound_type=primary.wound_type or secondary.wound_type,
        stage=primary.stage or secondary.stage,
        location=primary.location or secondary.location,
        length_cm=primary.length_cm if primary.length_cm is not None else secondary.length_cm,
        width_cm=primary.width_cm if primary.width_cm is not None else secondary.width_cm,
        depth_cm=primary.depth_cm if primary.depth_cm is not None else secondary.depth_cm,
        drainage_amount=primary.drainage_amount or secondary.drainage_amount,
        source=f"{primary.source}+{secondary.source}" if primary.source != secondary.source else primary.source,
        confidence=max(primary.confidence, secondary.confidence),
        raw_snippet=primary.raw_snippet or secondary.raw_snippet,
        evidence=evidence,
    )


def _parse_note(text: str) -> WoundExtraction:
    if is_soap_note(text):
        wound = parse_soap_note(text)
    elif is_multi_wound_note(text):
        wound = parse_multi_wound_note(text)
    elif is_prose_note(text):
        wound = parse_prose_note(text)
    else:
        wound = parse_wound_text(text, source="note_text", base_confidence=0.6)
    return collect_evidence_from_text(text, wound)


def extract_patient_wound(record: PatientRecord) -> WoundExtraction | None:
    candidates: list[WoundExtraction] = []

    for assessment in record.assessments:
        parsed = parse_assessment(assessment.get("raw_json"))
        if parsed:
            raw = assessment.get("raw_json") or ""
            candidates.append(collect_evidence_from_text(raw, parsed))

    for note in record.notes:
        text = note.get("note_text") or ""
        if text.strip():
            candidates.append(_parse_note(text))

    if not candidates:
        return None

    best = _pick_best(candidates)
    if best is None:
        return None

    sorted_candidates = sorted(
        candidates,
        key=lambda w: (w.is_complete(), w.confidence),
        reverse=True,
    )
    if len(sorted_candidates) >= 2:
        merged = _merge(sorted_candidates[0], sorted_candidates[1])
        if merged.is_complete():
            merged.confidence = max(merged.confidence, 0.85)
        if merged.confidence >= best.confidence or merged.is_complete():
            return merged

    if best.is_complete():
        best.confidence = max(best.confidence, 0.8)

    return best
