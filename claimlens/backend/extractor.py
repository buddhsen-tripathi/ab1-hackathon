"""
Wound data extraction from clinical notes and assessments.
Strategy:
  1. Structured assessments (raw_json) → direct parse, highest confidence
  2. Structured SPN/SOAP notes → regex extraction, high confidence
  3. Prose/Envive notes → Claude LLM extraction, variable confidence
"""
import re
import json
import os
import asyncio
from typing import Optional

import anthropic

_anthropic_client = None


def get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _anthropic_client


def llm_is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


WOUND_TYPE_MAP = {
    "pressure_ulcer": "Pressure Ulcer",
    "pressure ulcer": "Pressure Ulcer",
    "pressureulcer": "Pressure Ulcer",
    "diabetic_foot_ulcer": "Diabetic Foot Ulcer",
    "diabetic foot ulcer": "Diabetic Foot Ulcer",
    "diabetic": "Diabetic Foot Ulcer",
    "dfu": "Diabetic Foot Ulcer",
    "venous_ulcer": "Venous Ulcer",
    "venous stasis ulcer": "Venous Ulcer",
    "venous ulcer": "Venous Ulcer",
    "venous": "Venous Ulcer",
    "arterial_ulcer": "Arterial Ulcer",
    "arterial ulcer": "Arterial Ulcer",
    "arterial": "Arterial Ulcer",
    "surgical_wound": "Surgical Wound",
    "surgical wound": "Surgical Wound",
    "surgical site": "Surgical Wound",
    "abscess": "Abscess",
    "burn": "Burn",
}

# Terms that look like wound types but are actually wound descriptions / periwound conditions
NOT_WOUND_TYPES = {
    "erythematous", "erythema", "macerated", "maceration", "slough", "granulation",
    "necrotic", "eschar", "fibrinous", "epithelializing", "undermining", "tunneling",
    "periwound", "wound bed", "exudate", "serosanguineous", "sanguineous",
}

# ICD-10 prefix → wound type
ICD10_WOUND_MAP = {
    "L89": "Pressure Ulcer",
    "E10.6": "Diabetic Foot Ulcer",  # type 1 with complications
    "E11.6": "Diabetic Foot Ulcer",  # type 2 with complications
    "E10.62": "Diabetic Foot Ulcer",
    "E11.62": "Diabetic Foot Ulcer",
    "I83": "Venous Ulcer",
    "I70": "Arterial Ulcer",
    "T81": "Surgical Wound",
    "L02": "Abscess",
    "T30": "Burn",
    "T31": "Burn",
}

WOUND_TYPE_CANONICAL = {
    "Pressure Ulcer": "pressure_ulcer",
    "Diabetic Foot Ulcer": "diabetic_foot_ulcer",
    "Venous Ulcer": "venous_ulcer",
    "Arterial Ulcer": "arterial_ulcer",
    "Surgical Wound": "surgical_wound",
    "Abscess": "abscess",
    "Burn": "burn",
}

DRAINAGE_MAP = {
    "none": "none", "no drainage": "none", "dry": "none",
    "light": "light", "slight": "light", "scant": "light", "minimal": "light", "small": "light",
    "moderate": "moderate", "mod": "moderate",
    "heavy": "heavy", "large": "heavy", "copious": "heavy", "profuse": "heavy",
}


def normalize_wound_type(raw: str) -> Optional[str]:
    if not raw:
        return None
    key = raw.lower().strip().rstrip(",.")
    # Reject known non-wound-type terms
    if key in NOT_WOUND_TYPES:
        return None
    # try direct map
    mapped = WOUND_TYPE_MAP.get(key)
    if mapped:
        return mapped
    # substring match (longest key first to avoid false short matches)
    for k in sorted(WOUND_TYPE_MAP.keys(), key=len, reverse=True):
        if k in key:
            return WOUND_TYPE_MAP[k]
    # If it doesn't match any known wound type, don't blindly return it
    return None


def wound_type_from_icd10(diagnoses: list) -> Optional[str]:
    """Derive wound type from ICD-10 diagnosis codes when note extraction fails."""
    for dx in (diagnoses or []):
        code = (dx.get("icd10_code") or "").upper()
        desc = (dx.get("icd10_description") or "").lower()
        status = (dx.get("clinical_status") or "").lower()
        if status == "resolved":
            continue
        # Check ICD prefix map
        for prefix, wtype in ICD10_WOUND_MAP.items():
            if code.startswith(prefix):
                return wtype
        # Fallback: check description
        for kw, wtype in [
            ("pressure ulcer", "Pressure Ulcer"),
            ("pressure injury", "Pressure Ulcer"),
            ("diabetic foot", "Diabetic Foot Ulcer"),
            ("diabetic", "Diabetic Foot Ulcer"),
            ("venous", "Venous Ulcer"),
            ("arterial ulcer", "Arterial Ulcer"),
            ("surgical wound", "Surgical Wound"),
            ("abscess", "Abscess"),
            ("burn", "Burn"),
        ]:
            if kw in desc and "ulcer" in desc or kw in desc:
                return wtype
    return None


def normalize_drainage(raw: str) -> Optional[str]:
    if not raw:
        return None
    key = raw.lower().strip().rstrip(",.")
    for k, v in DRAINAGE_MAP.items():
        if k in key:
            return v
    return raw.lower()


def _flatten_assessment_json(data: dict) -> dict:
    """
    Flatten PCC assessment JSON which may be either:
      A) Flat format: {wound_type, stage, location, length_cm, ...}
      B) Sections/questions format: {sections: [{sectionName, questions: [{question, answer}]}]}
    Returns a flat dict of extracted fields.
    """
    # Format A: flat fields present
    if any(k in data for k in ("wound_type", "length_cm", "stage", "location")):
        return data

    # Format B: sections/questions
    flat = {}
    question_map = {
        # Question text → flat field name
        "wound type": "wound_type",
        "type": "wound_type",
        "stage": "stage",
        "location": "location",
        "laterality": "laterality",
        "length (cm)": "length_cm",
        "width (cm)": "width_cm",
        "depth (cm)": "depth_cm",
        "drainage present": "drainage",
        "drainage amount": "drainage_amount",
        "drainage type": "drainage_type",
        "wound narrative": "_narrative",
    }
    sections = data.get("sections", [])
    for section in sections:
        sname = (section.get("sectionName") or "").upper()
        for q in section.get("questions", []):
            qtext = (q.get("question") or "").lower().strip()
            answer = q.get("answer") or ""
            # Direct mapping
            for kw, field in question_map.items():
                if kw in qtext:
                    flat[field] = answer
                    break

    # Parse narrative field if present (e.g. "Diabetic to Left foot / Measures 5.3 cm x 4.5 cm")
    narrative = flat.pop("_narrative", None)
    if narrative:
        flat["_narrative_text"] = narrative
        # Extract from narrative using regex
        m = re.search(r"([\d.]+)\s*cm\s*[xX×]\s*([\d.]+)\s*cm", narrative)
        if m and "length_cm" not in flat:
            flat["length_cm"] = float(m.group(1))
            flat["width_cm"] = float(m.group(2))
        m3 = re.search(r"([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)\s*cm", narrative, re.IGNORECASE)
        if m3:
            flat["length_cm"] = float(m3.group(1))
            flat["width_cm"] = float(m3.group(2))
            flat["depth_cm"] = float(m3.group(3))
        # Extract wound type from narrative
        for kw, wt in [("diabetic", "diabetic_foot_ulcer"), ("pressure", "pressure_ulcer"),
                        ("venous", "venous_ulcer"), ("arterial", "arterial_ulcer"),
                        ("surgical", "surgical_wound"), ("abscess", "abscess"), ("burn", "burn")]:
            if kw in narrative.lower() and "wound_type" not in flat:
                flat["wound_type"] = wt
        # Extract drainage from narrative
        drain_m = re.search(r"(?:drainage|drain):\s*(\w+)", narrative, re.IGNORECASE)
        if drain_m and "drainage_amount" not in flat:
            flat["drainage_amount"] = drain_m.group(1)
        # Extract stage from narrative
        stage_m = re.search(r"stage[:\s]*(\d+|unstageable)", narrative, re.IGNORECASE)
        if stage_m and "stage" not in flat:
            flat["stage"] = stage_m.group(1)

    # Normalize numeric fields
    for f in ("length_cm", "width_cm", "depth_cm"):
        v = flat.get(f)
        if isinstance(v, str):
            try:
                flat[f] = float(v)
            except ValueError:
                flat.pop(f, None)

    return flat


def extract_from_assessment(assessment: dict) -> dict:
    """Parse structured raw_json from PCC assessment (handles flat and sections formats)."""
    try:
        raw_data = json.loads(assessment.get("raw_json") or "{}")
    except Exception:
        return {}

    data = _flatten_assessment_json(raw_data)

    raw_wt = str(data.get("wound_type", "") or "")
    wound_type = normalize_wound_type(raw_wt)
    stage_raw = data.get("stage")
    stage = str(stage_raw).strip() if stage_raw and str(stage_raw).strip() not in ("None", "N/A", "n/a", "") else None
    location = data.get("location") or data.get("laterality")
    if location and location.strip() in ("N/A", "n/a"):
        location = None
    length = data.get("length_cm")
    width = data.get("width_cm")
    depth = data.get("depth_cm")
    drainage_raw = data.get("drainage_amount") or data.get("drainage_type") or data.get("drainage")
    drainage = normalize_drainage(str(drainage_raw)) if drainage_raw else None

    evidence = {}
    src = data.get("_narrative_text")
    suffix = f'in assessment narrative: "{src[:60]}..."' if src else "in assessment raw_json"

    if wound_type:
        evidence["wound_type"] = f'"{raw_wt}" {suffix}'
    if stage:
        evidence["stage"] = f'"stage: {stage}" {suffix}'
    if location:
        evidence["location"] = f'"{location}" {suffix}'
    if length is not None:
        evidence["length"] = f'"{length} cm" {suffix}'
    if width is not None:
        evidence["width"] = f'"{width} cm" {suffix}'
    if depth is not None:
        evidence["depth"] = f'"{depth} cm" {suffix}'
    if drainage:
        evidence["drainage"] = f'"{drainage_raw}" {suffix}'

    return {
        "wound_type": wound_type,
        "wound_location": location,
        "wound_stage": stage,
        "length_cm": length,
        "width_cm": width,
        "depth_cm": depth,
        "drainage": drainage,
        "confidence": 0.95,
        "source": "assessment",
        "evidence": evidence,
    }


# Regex patterns for structured SPN/SOAP notes
_PATTERNS = {
    "wound_type": [
        # Must contain a known wound-type keyword to be valid
        r"(?:Wound\s+Type|Type):\s*([^\n,]+?(?:ulcer|wound|abscess|burn|diabetic|pressure|venous|arterial)[^\n,]*?)(?:\s*,\s*Stage|\s*Stage|\n|$)",
        r"(?:Diagnosis|Dx):\s*([^\n]+(?:ulcer|wound|abscess|burn)[^\n]*)",
    ],
    "location": [
        r"Location:\s*([^\n]+)",
        r"(?:wound|ulcer)\s+(?:at|on|to)\s+(?:the\s+)?([A-Za-z\s]+?)(?:\.|,|\n|$)",
    ],
    "stage": [
        r"Stage[:\s]+(\d+|[Ii][Vv]|[Ii][Ii][Ii]|[Ii][Ii]|[Ii]|unstageable)",
        r"(?:Wound\s+Type|Type):[^\n]*Stage\s*(\d+)",
        r"stage\s*(\d+)",
    ],
    "length_cm": [
        r"Length:\s*([\d.]+)\s*cm",
        r"([\d.]+)\s*cm\s*[xX×]\s*[\d.]+\s*cm",
    ],
    "width_cm": [
        r"Width:\s*([\d.]+)\s*cm",
        r"[\d.]+\s*cm\s*[xX×]\s*([\d.]+)\s*cm",
    ],
    "depth_cm": [
        r"Depth:\s*([\d.]+)\s*cm",
        r"[\d.]+\s*cm\s*[xX×]\s*[\d.]+\s*cm\s*[xX×]\s*([\d.]+)\s*cm",
    ],
    "measurements_compact": [
        r"Meas(?:urements?)?\s*(?:aprx\.?|approx(?:imately)?\.?)?\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*cm",
        r"([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)\s*cm",
    ],
    "drainage": [
        r"Drainage(?:\s+Amount)?:\s*([^\n]+)",
        r"(?:drainage|exudate)(?:\s+is|\s*:)\s*([^\n,\.]+)",
    ],
}

# Keywords that indicate it's a wound note at all
WOUND_KEYWORDS = [
    "ulcer", "wound", "pressure", "diabetic foot", "venous", "arterial",
    "surgical", "abscess", "burn", "stage", "sacr", "heel", "ankle",
    "meas", "drainage", "length:", "width:", "depth:"
]


def _find_pattern(text: str, patterns: list) -> Optional[tuple]:
    """Return (value, matched_text) for first matching pattern."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip(), m.group(0).strip()
    return None


def extract_from_note_regex(note: dict) -> dict:
    """Extract wound fields from structured note text using regex."""
    text = note.get("note_text") or ""
    if not text:
        return {}

    # Check if this looks like a wound note
    has_wound_content = any(kw in text.lower() for kw in WOUND_KEYWORDS)
    if not has_wound_content:
        return {}

    evidence = {}

    # Wound type
    wt_result = _find_pattern(text, _PATTERNS["wound_type"])
    wound_type = normalize_wound_type(wt_result[0]) if wt_result else None
    if wt_result:
        evidence["wound_type"] = f'"{wt_result[1]}"'

    # Location
    loc_result = _find_pattern(text, _PATTERNS["location"])
    location = loc_result[0].rstrip(".,") if loc_result else None
    if loc_result:
        evidence["location"] = f'"{loc_result[1]}"'

    # Stage
    stage_result = _find_pattern(text, _PATTERNS["stage"])
    stage = stage_result[0] if stage_result else None
    if stage_result:
        evidence["stage"] = f'"{stage_result[1]}"'

    # Measurements — try compact format first
    length = width = depth = None
    meas_match = None
    for pat in _PATTERNS["measurements_compact"]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            length, width, depth = float(m.group(1)), float(m.group(2)), float(m.group(3))
            meas_match = m.group(0)
            evidence["length"] = f'"{meas_match}" (L)'
            evidence["width"] = f'"{meas_match}" (W)'
            evidence["depth"] = f'"{meas_match}" (D)'
            break

    if length is None:
        lr = _find_pattern(text, _PATTERNS["length_cm"])
        if lr:
            length = float(lr[0])
            evidence["length"] = f'"{lr[1]}"'
    if width is None:
        wr = _find_pattern(text, _PATTERNS["width_cm"])
        if wr:
            width = float(wr[0])
            evidence["width"] = f'"{wr[1]}"'
    if depth is None:
        dr2 = _find_pattern(text, _PATTERNS["depth_cm"])
        if dr2:
            depth = float(dr2[0])
            evidence["depth"] = f'"{dr2[1]}"'

    # Drainage
    drain_result = _find_pattern(text, _PATTERNS["drainage"])
    drainage_raw = drain_result[0] if drain_result else None
    drainage = normalize_drainage(drainage_raw) if drainage_raw else None
    if drain_result:
        evidence["drainage"] = f'"{drain_result[1]}"'

    # Confidence: how many fields did we find?
    found = sum(1 for x in [wound_type, location, length, width, depth, drainage] if x)
    confidence = 0.5 + (found / 6) * 0.4  # 0.5 base, up to 0.9

    # Is this a structured note or more free-form?
    is_structured = bool(re.search(r"(?:Location|Length|Width|Depth|Drainage):", text, re.IGNORECASE))
    note_format = "structured_spn" if is_structured else "prose"

    return {
        "wound_type": wound_type,
        "wound_location": location,
        "wound_stage": stage,
        "length_cm": length,
        "width_cm": width,
        "depth_cm": depth,
        "drainage": drainage,
        "confidence": round(confidence, 2),
        "source": f"note_{note_format}",
        "note_format": note_format,
        "evidence": evidence,
    }


LLM_EXTRACTION_PROMPT = """You are a clinical data extractor for a Medicare Part B wound care billing system.
Extract wound information from the clinical note below and return ONLY a valid JSON object.

Clinical Note:
{note_text}

Return a JSON object with exactly these fields (use null if not found or not applicable):
{{
  "wound_type": <one of: "pressure_ulcer", "diabetic_foot_ulcer", "venous_ulcer", "arterial_ulcer", "surgical_wound", "abscess", "burn", or null>,
  "location": <string describing wound location, e.g. "Sacrum", "Left heel", null>,
  "stage": <string "2", "3", "4", or "unstageable" for pressure ulcers only, otherwise null>,
  "length_cm": <number in cm, null if not found>,
  "width_cm": <number in cm, null if not found>,
  "depth_cm": <number in cm, null if not found>,
  "drainage": <one of: "none", "light", "moderate", "heavy", null>,
  "confidence": <number 0.0-1.0 reflecting extraction confidence>,
  "evidence": {{
    "wound_type": <exact quote from note, or null>,
    "location": <exact quote, or null>,
    "stage": <exact quote, or null>,
    "length_cm": <exact quote, or null>,
    "width_cm": <exact quote, or null>,
    "depth_cm": <exact quote, or null>,
    "drainage": <exact quote, or null>
  }}
}}

Return ONLY the JSON, no other text."""


async def extract_from_note_llm(note: dict) -> dict:
    """Use Claude to extract wound fields from unstructured notes."""
    text = note.get("note_text") or ""
    if not text or len(text.strip()) < 20:
        return {}

    if not llm_is_configured():
        return {}
    client = get_anthropic_client()
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": LLM_EXTRACTION_PROMPT.format(note_text=text[:3000])
                }]
            )
        )
        raw = response.content[0].text.strip()
        # Strip markdown code blocks if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)

        evidence = data.get("evidence", {})
        ev = {}
        for field in ["wound_type", "location", "stage", "length_cm", "width_cm", "depth_cm", "drainage"]:
            if evidence.get(field):
                ev[field] = f'"{evidence[field]}" (LLM extracted)'

        return {
            "wound_type": normalize_wound_type(data.get("wound_type") or ""),
            "wound_location": data.get("location"),
            "wound_stage": str(data.get("stage")) if data.get("stage") else None,
            "length_cm": data.get("length_cm"),
            "width_cm": data.get("width_cm"),
            "depth_cm": data.get("depth_cm"),
            "drainage": normalize_drainage(data.get("drainage") or ""),
            "confidence": float(data.get("confidence", 0.7)),
            "source": "note_llm",
            "note_format": "envive",
            "evidence": ev,
        }
    except Exception as e:
        print(f"LLM extraction failed: {e}")
        return {}


SUMMARY_PROMPT = """You are assisting a Medicare Part B wound-care biller.
Write a concise, factual 2-3 sentence claim-readiness summary from the structured packet below.
State the routing decision, strongest evidence, documentation gaps, and next action.
Do not invent facts and do not provide medical advice. Return plain text only.

Packet:
{packet}
"""


async def generate_patient_summary(patient: dict) -> str:
    """Generate a concise biller-facing narrative from an already-scored packet."""
    if not llm_is_configured():
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    packet = {
        "patient_id": patient.get("patient_id"),
        "coverage": "Active Medicare Part B" if patient.get("has_medicare_part_b") else "No active Medicare Part B",
        "wound_type": patient.get("wound_type"),
        "location": patient.get("wound_location"),
        "stage": patient.get("wound_stage"),
        "measurements_cm": {
            "length": patient.get("length_cm"),
            "width": patient.get("width_cm"),
            "depth": patient.get("depth_cm"),
        },
        "drainage": patient.get("drainage"),
        "claim_score": patient.get("claim_score"),
        "routing_decision": patient.get("routing_decision"),
        "missing_fields": patient.get("missing_fields") or [],
        "routing_reason": patient.get("routing_reason"),
        "biller_action": patient.get("biller_action"),
    }
    client = get_anthropic_client()
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=220,
            messages=[{
                "role": "user",
                "content": SUMMARY_PROMPT.format(packet=json.dumps(packet, indent=2)),
            }],
        ),
    )
    return response.content[0].text.strip()


def merge_extractions(assessment_result: dict, note_result: dict) -> dict:
    """
    Merge extraction from assessment (highest priority) and note.
    Assessment fields take precedence; fill gaps from note.
    """
    if not assessment_result and not note_result:
        return {}

    base = {**note_result, **{k: v for k, v in assessment_result.items() if v is not None and v != {}}}

    # Merge evidence traces
    ev = {}
    ev.update(note_result.get("evidence", {}))
    ev.update(assessment_result.get("evidence", {}))
    base["evidence"] = ev

    # Source priority
    if assessment_result.get("wound_type"):
        base["source"] = "assessment"
    elif note_result.get("source"):
        base["source"] = note_result["source"]

    # Confidence: take max
    base["confidence"] = max(
        assessment_result.get("confidence", 0),
        note_result.get("confidence", 0)
    )

    return base


def detect_multi_wound(notes: list) -> list:
    """Detect if notes describe multiple wounds and extract them all."""
    wounds = []
    seen = set()
    for note in notes:
        text = note.get("note_text") or ""
        # PCC prose format: a primary wound followed by a shorthand heel wound.
        primary_pattern = re.compile(
            r"(?P<type>Pressure\s+Ulcer|Diabetic|Venous|Arterial|Surgical|Abscess|Burn)\s+"
            r"(?P<location>[A-Za-z ]+?)\s+measures\s+(?:aprx\.?|approx(?:imately)?\.?)?\s*"
            r"(?P<length>[\d.]+)\s*[xX×]\s*(?P<width>[\d.]+)\s*cm,?\s*depth\s*"
            r"(?P<depth>[\d.]+)\s*cm",
            re.IGNORECASE,
        )
        secondary_pattern = re.compile(
            r"Heel\s+wound\s+also\s+eval\s*-\s*(?P<location>[A-Za-z ]+?)\s+"
            r"(?P<length>[\d.]+)\s*[xX×]\s*(?P<width>[\d.]+),?\s*"
            r"(?P<depth>[\d.]+)\s*cm\s+deep",
            re.IGNORECASE,
        )
        primary_match = primary_pattern.search(text)
        secondary_match = secondary_pattern.search(text)
        if primary_match and secondary_match:
            for index, match in enumerate([primary_match, secondary_match], 1):
                is_secondary = match is secondary_match
                raw_type = "Pressure Ulcer" if is_secondary else primary_match.group("type")
                nearby = text[match.end():match.end() + 100]
                amount_match = re.search(r"(none|no|scant|minimal|min|slight|light|moderate|heavy|copious)\s+(?:\w+\s+)?drainage", nearby, re.IGNORECASE)
                result = {
                    "wound_type": normalize_wound_type(raw_type),
                    "wound_location": match.group("location").strip().replace("L ", "Left ").replace("R ", "Right "),
                    "wound_stage": None,
                    "length_cm": float(match.group("length")),
                    "width_cm": float(match.group("width")),
                    "depth_cm": float(match.group("depth")),
                    "drainage": normalize_drainage(amount_match.group(1)) if amount_match else None,
                    "confidence": 0.88,
                    "source": "note_multi_wound",
                    "note_format": "multi_wound",
                    "evidence": {"measurements": f'"{match.group(0)}"'},
                    "wound_number": index,
                }
                key = (result["wound_type"], result["length_cm"], result["width_cm"], result["depth_cm"])
                if key not in seen:
                    seen.add(key)
                    wounds.append(result)
        # Look for multiple wound sections
        # Patterns like "Wound #1", "Wound 1:", "Second wound", numbered sections
        sections = re.split(
            r"(?:wound\s*[#\-]?\s*[12]|first\s+wound|second\s+wound|additional\s+wound)",
            text, flags=re.IGNORECASE
        )
        if len(sections) > 1:
            for i, section in enumerate(sections[1:], 1):
                # Extract from each section
                pseudo_note = {"note_text": section[:500]}
                result = extract_from_note_regex(pseudo_note)
                if result.get("wound_type"):
                    result["wound_number"] = i
                    key = (result.get("wound_type"), result.get("length_cm"), result.get("width_cm"), result.get("depth_cm"))
                    if key not in seen:
                        seen.add(key)
                        wounds.append(result)

        # Prose multi-wound notes often identify wounds by repeated measurements
        # rather than numbered headings. Use a local context window per LxWxD tuple.
        dimension_pattern = re.compile(
            r"([\d.]+)\s*(?:cm\s*)?[xX×]\s*([\d.]+)\s*(?:cm\s*)?[xX×]\s*([\d.]+)\s*cm",
            re.IGNORECASE,
        )
        matches = list(dimension_pattern.finditer(text))
        if len(matches) >= 2:
            for index, match in enumerate(matches, 1):
                context = text[max(0, match.start() - 100):min(len(text), match.end() + 120)]
                context_lower = context.lower()
                wound_type = None
                for phrase in sorted(WOUND_TYPE_MAP, key=len, reverse=True):
                    if phrase in context_lower:
                        wound_type = WOUND_TYPE_MAP[phrase]
                        break
                if not wound_type and "heel wound" in context_lower:
                    wound_type = "Pressure Ulcer"
                if not wound_type:
                    continue

                location = None
                for candidate in ["left foot", "right foot", "left ankle", "right ankle", "left heel", "right heel", "sacrum", "sacral region", "coccyx"]:
                    if candidate in context_lower:
                        location = candidate.title()
                        break
                stage_match = re.search(r"stage\s*(2|3|4|unstageable)", context, re.IGNORECASE)
                drainage_match = re.search(r"(none|no|scant|minimal|light|moderate|heavy|copious)\s+(?:\w+\s+)?drainage", context, re.IGNORECASE)
                result = {
                    "wound_type": wound_type,
                    "wound_location": location,
                    "wound_stage": stage_match.group(1).lower() if stage_match else None,
                    "length_cm": float(match.group(1)),
                    "width_cm": float(match.group(2)),
                    "depth_cm": float(match.group(3)),
                    "drainage": normalize_drainage(drainage_match.group(1)) if drainage_match else None,
                    "confidence": 0.82,
                    "source": "note_multi_wound",
                    "note_format": "multi_wound",
                    "evidence": {"measurements": f'"{match.group(0)}"'},
                    "wound_number": index,
                }
                key = (result["wound_type"], result["length_cm"], result["width_cm"], result["depth_cm"])
                if key not in seen:
                    seen.add(key)
                    wounds.append(result)

    return wounds if len(wounds) >= 2 else []


def select_primary_wound(wounds: list) -> Optional[dict]:
    """
    Select primary wound: most complete + most severe + largest volume.
    """
    if not wounds:
        return None
    if len(wounds) == 1:
        return wounds[0]

    def score_wound(w):
        completeness = sum(1 for f in ["wound_type", "wound_location", "wound_stage", "length_cm", "width_cm", "depth_cm", "drainage"]
                          if w.get(f) is not None)
        severity = {"4": 4, "3": 3, "unstageable": 3, "2": 2, "1": 1}.get(str(w.get("wound_stage", "")), 0)
        volume = (w.get("length_cm") or 0) * (w.get("width_cm") or 0) * max(w.get("depth_cm") or 0.1, 0.1)
        return (completeness * 10) + (severity * 5) + volume

    return max(wounds, key=score_wound)
