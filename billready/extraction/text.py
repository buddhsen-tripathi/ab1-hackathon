from __future__ import annotations

import re

from billready.models import WoundExtraction

WOUND_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"pressure\s+ulcer", "pressure ulcer"),
    (r"diabetic\s+foot\s+ulcer", "diabetic foot ulcer"),
    (r"venous\s+stasis\s+ulcer", "venous stasis ulcer"),
    (r"venous\s+ulcer", "venous ulcer"),
    (r"arterial\s+ulcer", "arterial ulcer"),
    (r"surgical\s+site\s+infection", "surgical site infection"),
    (r"\babscess\b", "abscess"),
    (r"\bburn\b", "burn"),
]

STAGE_PATTERN = re.compile(
    r"stage\s*(?:[:.]?\s*)?(?:stage\s*)?(\d|unstageable|unstageable)",
    re.IGNORECASE,
)

# SOAP labeled: Length: 3.2 cm  Width: 2.1 cm  Depth: 0.4 cm
LABELED_DIMS = re.compile(
    r"Length:\s*([\d.]+)\s*cm.*?Width:\s*([\d.]+)\s*cm(?:.*?Depth:\s*([\d.]+)\s*cm)?",
    re.IGNORECASE | re.DOTALL,
)

# Prose / Envive: Measures 2.9 cm x 2.8 cm or Meas 4.2x3.1x1.5cm
MEASURES_PATTERN = re.compile(
    r"(?:Measures|Meas\.?)\s*([\d.]+)\s*(?:cm\s*)?[x×]\s*([\d.]+)\s*(?:cm\s*)?"
    r"(?:[x×]\s*([\d.]+)\s*(?:cm)?)?",
    re.IGNORECASE,
)

# Loose L x W x D with optional cm
LOOSE_DIMS = re.compile(
    r"([\d.]+)\s*(?:cm\s*)?[x×]\s*([\d.]+)\s*(?:cm\s*)?[x×]\s*([\d.]+)\s*cm",
    re.IGNORECASE,
)

DRAINAGE_PATTERN = re.compile(
    r"Drainage(?:\s+amount)?\s*:\s*([^.\n]+)",
    re.IGNORECASE,
)

DRAINAGE_AMOUNT_KEYWORDS = {
    "none": ("none", "no drainage", "dry"),
    "light": ("light", "minimal", "scant", "min"),
    "moderate": ("moderate", "mod"),
    "heavy": ("heavy", "large", "copious"),
}


def normalize_drainage(text: str | None) -> str | None:
    if not text:
        return None
    lower = text.lower()
    for amount, keywords in DRAINAGE_AMOUNT_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return amount
    return None


ENVIVE_TYPE_PATTERN = re.compile(
    r"Wound Status:\s*([A-Za-z\s]+?)\s+to\s+",
    re.IGNORECASE,
)

ENVIVE_TYPE_MAP = {
    "pressure ulcer": "pressure ulcer",
    "diabetic foot ulcer": "diabetic foot ulcer",
    "diabetic": "diabetic foot ulcer",
    "venous stasis ulcer": "venous stasis ulcer",
    "venous": "venous ulcer",
    "arterial": "arterial ulcer",
    "surgical": "surgical site infection",
    "abscess": "abscess",
    "burn": "burn",
}


def extract_wound_type(text: str) -> str | None:
    envive = ENVIVE_TYPE_PATTERN.search(text)
    if envive:
        key = envive.group(1).strip().lower()
        for prefix, label in ENVIVE_TYPE_MAP.items():
            if key.startswith(prefix) or key == prefix:
                return label

    inline_type = re.search(
        r"(pressure ulcer|diabetic foot ulcer|venous stasis ulcer|venous ulcer|"
        r"arterial ulcer|surgical site infection|abscess|burn)\b",
        text,
        re.IGNORECASE,
    )
    if inline_type:
        matched = inline_type.group(1).lower()
        for pattern, label in WOUND_TYPE_PATTERNS:
            if re.fullmatch(pattern.replace(r"\s+", r"\\s+"), matched) or label == matched:
                return label
        return matched

    lower = text.lower()
    for pattern, label in WOUND_TYPE_PATTERNS:
        if re.search(pattern, lower):
            return label
    return None


def extract_stage(text: str) -> str | None:
    match = STAGE_PATTERN.search(text)
    if not match:
        return None
    value = match.group(1).lower()
    if value == "unstageable":
        return "unstageable"
    return value


def extract_location(text: str) -> str | None:
    labeled = re.search(r"Location:\s*([^\n]+)", text, re.IGNORECASE)
    if labeled:
        return labeled.group(1).strip()

    # Envive: "Wound Status: Pressure Ulcer to Right hip / ..."
    envive = re.search(r"Wound Status:[^/]*?\sto\s+([^/\n]+)", text, re.IGNORECASE)
    if envive:
        return envive.group(1).strip()

    to_match = re.search(
        r"(?:pressure\s+ulcer|diabetic\s+foot\s+ulcer|venous\s+ulcer|wound)\s+to\s+([^/\n]+)",
        text,
        re.IGNORECASE,
    )
    if to_match:
        return to_match.group(1).strip()

    return None


def extract_measurements(text: str) -> tuple[float | None, float | None, float | None]:
    labeled = LABELED_DIMS.search(text)
    if labeled:
        depth = float(labeled.group(3)) if labeled.group(3) else None
        return float(labeled.group(1)), float(labeled.group(2)), depth

    measures = MEASURES_PATTERN.search(text)
    if measures:
        depth = float(measures.group(3)) if measures.group(3) else None
        return float(measures.group(1)), float(measures.group(2)), depth

    loose = LOOSE_DIMS.search(text)
    if loose:
        return float(loose.group(1)), float(loose.group(2)), float(loose.group(3))

    return None, None, None


def extract_drainage(text: str) -> str | None:
    match = DRAINAGE_PATTERN.search(text)
    if match:
        return normalize_drainage(match.group(1))

    # Envive inline: "Drainage present - serosanguineous, heavy"
    inline = re.search(
        r"drainage(?:\s+present)?[^.\n]*?(none|light|moderate|heavy)",
        text,
        re.IGNORECASE,
    )
    if inline:
        return normalize_drainage(inline.group(1))

    # Trailing after slash: "/ Drainage: serosanguineous, heavy"
    slash = re.search(r"/\s*Drainage:\s*([^/\n]+)", text, re.IGNORECASE)
    if slash:
        return normalize_drainage(slash.group(1))

    return None


def _calibrate_confidence(
    source: str,
    fields_found: int,
    base_confidence: float,
    is_complete: bool,
) -> float:
    if fields_found == 0:
        return 0.0
    confidence = base_confidence * (fields_found / 5)
    if is_complete:
        if "assessment_structured" in source or "note_soap" in source:
            confidence = max(confidence, 0.95)
        elif "assessment" in source:
            confidence = max(confidence, 0.88)
        else:
            confidence = max(confidence, 0.8)
    return round(confidence, 2)


def parse_wound_text(text: str, source: str, base_confidence: float = 0.7) -> WoundExtraction:
    """Extract wound fields from free-text clinical narrative."""
    wound_type = extract_wound_type(text)
    stage = extract_stage(text)
    location = extract_location(text)
    length, width, depth = extract_measurements(text)
    drainage = extract_drainage(text)

    fields_found = sum(
        1
        for v in (wound_type, length, width, depth, drainage)
        if v is not None
    )
    is_complete = all(v is not None for v in (wound_type, length, width, depth, drainage))
    confidence = _calibrate_confidence(source, fields_found, base_confidence, is_complete)

    return WoundExtraction(
        wound_type=wound_type,
        stage=stage,
        location=location,
        length_cm=length,
        width_cm=width,
        depth_cm=depth,
        drainage_amount=drainage,
        source=source,
        confidence=confidence,
        raw_snippet=text[:300] if text else None,
    )
