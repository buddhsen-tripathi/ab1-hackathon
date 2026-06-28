from __future__ import annotations

import json
import re

from billready.extraction.text import normalize_drainage, parse_wound_text
from billready.models import WoundExtraction

WOUND_TYPE_MAP = {
    "pressure_ulcer": "pressure ulcer",
    "diabetic_foot_ulcer": "diabetic foot ulcer",
    "venous_stasis_ulcer": "venous stasis ulcer",
    "venous_ulcer": "venous ulcer",
    "arterial_ulcer": "arterial ulcer",
    "surgical_site_infection": "surgical site infection",
    "abscess": "abscess",
    "burn": "burn",
}


def _from_flat_json(data: dict) -> WoundExtraction:
    wound_type = data.get("wound_type")
    if wound_type:
        wound_type = WOUND_TYPE_MAP.get(wound_type, wound_type.replace("_", " "))

    stage = data.get("stage")
    if stage is not None:
        stage = str(stage)

    drainage = data.get("drainage_amount")
    if drainage:
        drainage = normalize_drainage(str(drainage)) or str(drainage).lower()

    return WoundExtraction(
        wound_type=wound_type,
        stage=stage,
        location=data.get("location"),
        length_cm=_to_float(data.get("length_cm")),
        width_cm=_to_float(data.get("width_cm")),
        depth_cm=_to_float(data.get("depth_cm")),
        drainage_amount=drainage,
        source="assessment_structured",
        confidence=0.98,
    )


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_narratives(data: dict) -> list[str]:
    narratives: list[str] = []

    for key in ("wound_narrative", "narrative", "wound_description"):
        if key in data and isinstance(data[key], str):
            narratives.append(data[key])

    sections = data.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            questions = section.get("questions") or section.get("fields") or []
            for q in questions:
                if not isinstance(q, dict):
                    continue
                answer = q.get("answer") or q.get("value")
                question = str(q.get("question") or q.get("label") or "").lower()
                if isinstance(answer, str) and (
                    "wound" in question or "narrative" in question or len(answer) > 40
                ):
                    narratives.append(answer)

    return narratives


def _best_structured_fields(data: dict) -> WoundExtraction | None:
    """Walk nested JSON for explicit measurement fields."""
    candidates: list[dict] = [data]

    sections = data.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict):
                candidates.append(section)
                for q in section.get("questions") or []:
                    if isinstance(q, dict):
                        candidates.append(q)

    flat: dict = {}
    for obj in candidates:
        for key in (
            "wound_type",
            "stage",
            "location",
            "length_cm",
            "width_cm",
            "depth_cm",
            "drainage_amount",
        ):
            if key in obj and obj[key] is not None and key not in flat:
                flat[key] = obj[key]

    if flat.get("length_cm") or flat.get("wound_type"):
        return _from_flat_json(flat)
    return None


def parse_assessment(raw_json: str | None) -> WoundExtraction | None:
    if not raw_json:
        return None

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    if "wound_type" in data or "length_cm" in data:
        return _from_flat_json(data)

    structured = _best_structured_fields(data)
    if structured and structured.is_complete():
        return structured

    narratives = _collect_narratives(data)
    if narratives:
        best: WoundExtraction | None = None
        for narrative in narratives:
            parsed = parse_wound_text(narrative, source="assessment_narrative", base_confidence=0.85)
            if best is None or parsed.confidence > best.confidence:
                best = parsed
        if best and (best.confidence > 0 or structured):
            if structured:
                return _merge_extractions(structured, best)
            return best

    return structured


def _merge_extractions(primary: WoundExtraction, secondary: WoundExtraction) -> WoundExtraction:
    """Fill gaps in primary from secondary."""
    return WoundExtraction(
        wound_type=primary.wound_type or secondary.wound_type,
        stage=primary.stage or secondary.stage,
        location=primary.location or secondary.location,
        length_cm=primary.length_cm if primary.length_cm is not None else secondary.length_cm,
        width_cm=primary.width_cm if primary.width_cm is not None else secondary.width_cm,
        depth_cm=primary.depth_cm if primary.depth_cm is not None else secondary.depth_cm,
        drainage_amount=primary.drainage_amount or secondary.drainage_amount,
        source=f"{primary.source}+{secondary.source}",
        confidence=max(primary.confidence, secondary.confidence),
        raw_snippet=primary.raw_snippet or secondary.raw_snippet,
    )
