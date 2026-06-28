"""Format detection + one parser per format, all returning WoundExtraction(s).

Tiers by trust: structured-field reader (assessment Q/A) > regex (SOAP /
Envive-slash) > regex best-effort (shorthand prose, multi-wound).
"""
import json
import re

from . import normalize as N
from .schema import WoundExtraction

# --- small location helpers ----------------------------------------------

_TYPE_WORDS = re.compile(
    r"\b(pressure|ulcer|injury|wound|decubitus|diabetic|neuropathic|venous|"
    r"stasis|arterial|ischemic|surgical|incision|abscess|burn|status)\b",
    re.IGNORECASE,
)
_LOC_AFTER_TO = re.compile(r"\bto\s+([A-Za-z][A-Za-z \-]+?)\s*(?:/|$|\n|\.)", re.I)
_LOC_BEFORE_MEASURES = re.compile(r"([A-Za-z][A-Za-z \-]+?)\s+measures\b", re.I)
_DRAINAGE_CLAUSE = re.compile(r"drainage[^\n.]*", re.IGNORECASE)
_PCT = lambda kw: re.compile(rf"(\d+)\s*%?\s*{kw}", re.IGNORECASE)
_SLOUGH_RE = _PCT("slough")
_GRAN_RE = _PCT("granulation")
_PERIWOUND_RE = re.compile(r"periwound[:\s]+([A-Za-z]+)", re.IGNORECASE)


def _strip_type_words(phrase):
    if not phrase:
        return None
    cleaned = _TYPE_WORDS.sub("", phrase)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned or None


def _drainage_clause(text):
    m = _DRAINAGE_CLAUSE.search(text or "")
    return m.group(0) if m else ""


def _wound_bed_extra(text):
    extra = {}
    for rx, key in ((_SLOUGH_RE, "slough_pct"), (_GRAN_RE, "granulation_pct")):
        m = rx.search(text or "")
        if m:
            extra[key] = int(m.group(1))
    pm = _PERIWOUND_RE.search(text or "")
    if pm:
        extra["periwound"] = pm.group(1).lower()
    return extra


# --- assessment shape detection ------------------------------------------

def detect_assessment(raw_json):
    """Return (shape, parsed_or_text). shape in
    {assessment_structured, assessment_narrative, unknown}."""
    if not raw_json:
        return "unknown", None
    try:
        j = json.loads(raw_json)
    except Exception:
        return "unknown", None
    sections = j.get("sections", [])
    for s in sections:
        for q in s.get("questions", []):
            if "narrative" in (q.get("question") or "").lower() and isinstance(
                q.get("answer"), str
            ):
                return "assessment_narrative", q["answer"]
    return "assessment_structured", j


# --- note format detection -----------------------------------------------

def detect_note_format(text):
    low = (text or "").lower()
    if "envive" in low or "wound status:" in low:
        return "note_envive"
    if "subjective:" in low and "objective:" in low:
        return "note_soap"
    return "note_shorthand"


# --- parsers --------------------------------------------------------------

def parse_structured_assessment(patient_id, doc_id, j):
    qa = {}
    for s in j.get("sections", []):
        sec = s.get("sectionName")
        for q in s.get("questions", []):
            qa[(sec, (q.get("question") or "").strip())] = q.get("answer")

    def get(section, question):
        return qa.get((section, question))

    location = get("LOCATION", "Location")
    lat_field = N.normalize_laterality(get("LOCATION", "Laterality") or "")
    loc_side = N.normalize_laterality(location or "")
    ext = WoundExtraction(
        patient_id=patient_id,
        source_doc="assessment",
        source_doc_id=doc_id,
        source_format="assessment_structured",
        method="structured_field",
        wound_type=N.normalize_wound_type(get("WOUND", "Wound Type") or ""),
        stage=N.normalize_stage(f"stage: {get('WOUND', 'Stage')}"),
        location=location,
        laterality=lat_field or loc_side,
        length_cm=N.to_float(get("WOUND", "Length (cm)")),
        width_cm=N.to_float(get("WOUND", "Width (cm)")),
        depth_cm=N.to_float(get("WOUND", "Depth (cm)")),
        drainage_amount=N.normalize_drainage(get("DRAINAGE", "Drainage Amount") or ""),
        drainage_type=(get("DRAINAGE", "Drainage Type") or "").lower() or None,
        confidence=0.97,
        raw_span=json.dumps({k[1]: v for k, v in qa.items()})[:500],
        extra=_wound_bed_extra(
            f"{get('WOUND_BED','Slough %')}% slough "
            f"{get('WOUND_BED','Granulation %')}% granulation "
            f"periwound: {get('WOUND_BED','Periwound')}"
        ),
    )
    # laterality conflict: side named in Location vs the Laterality field
    if loc_side and lat_field and loc_side != lat_field:
        ext._flag("laterality_conflict")
        ext.confidence = 0.9
    return [ext.finalize()]


def parse_envive(patient_id, doc_id, source_format, text):
    """Envive slash grammar: '<Type> to <Loc> / Measures L x W / Stage: S /
    Drainage: type, amount'. Used by note_envive and assessment_narrative."""
    method = "regex"
    loc_m = _LOC_AFTER_TO.search(text)
    location = (loc_m.group(1).strip() if loc_m else None) or N.find_location(text)
    clause = _drainage_clause(text)
    meas = N.find_measurements(text)
    first = meas[0] if meas else {}
    ext = WoundExtraction(
        patient_id=patient_id,
        source_doc="assessment" if source_format == "assessment_narrative" else "note",
        source_doc_id=doc_id,
        source_format=source_format,
        method=method,
        wound_type=N.normalize_wound_type(text),
        stage=N.normalize_stage(text),
        location=location,
        laterality=N.normalize_laterality(location or text),
        length_cm=first.get("length_cm"),
        width_cm=first.get("width_cm"),
        depth_cm=first.get("depth_cm"),
        drainage_amount=N.normalize_drainage(clause),
        drainage_type=N.normalize_drainage_type(clause),
        confidence=0.8,
        raw_span=text[:500],
    )
    if first.get("implausible"):
        ext._flag("implausible_measurement")
    return [ext.finalize()]


def parse_soap(patient_id, doc_id, text):
    clean, _ = N.clean_text(text)
    loc_m = _LOC_BEFORE_MEASURES.search(clean)
    location = N.find_location(clean) or (
        _strip_type_words(loc_m.group(1)) if loc_m else None
    )
    clause = _drainage_clause(clean)
    meas = N.find_measurements(clean)
    first = meas[0] if meas else {}
    ext = WoundExtraction(
        patient_id=patient_id,
        source_doc="note",
        source_doc_id=doc_id,
        source_format="note_soap",
        method="regex",
        wound_type=N.normalize_wound_type(clean),
        stage=N.normalize_stage(clean),
        location=location,
        laterality=N.normalize_laterality(loc_m.group(1) if loc_m else clean),
        length_cm=first.get("length_cm"),
        width_cm=first.get("width_cm"),
        depth_cm=first.get("depth_cm"),
        drainage_amount=N.normalize_drainage(clause),
        drainage_type=N.normalize_drainage_type(clean),
        confidence=0.85,
        raw_span=text[:500],
        extra=_wound_bed_extra(clean),
    )
    if first.get("implausible"):
        ext._flag("implausible_measurement")
    return [ext.finalize()]


def parse_shorthand(patient_id, doc_id, text):
    clean, _ = N.clean_text(text)
    meas = N.find_measurements(clean)
    if not meas:
        ext = WoundExtraction(
            patient_id=patient_id, source_doc="note", source_doc_id=doc_id,
            source_format="note_shorthand", method="regex",
            wound_type=N.normalize_wound_type(clean), confidence=0.4,
            raw_span=text[:500],
        )
        ext._flag("unparseable")
        return [ext.finalize()]

    multi = len(meas) > 1
    results = []
    for idx, m in enumerate(meas):
        # context window around this measurement cluster
        pos = clean.find(m["span"])
        window = clean[max(0, pos - 70): pos + len(m["span"]) + 45]
        ext = WoundExtraction(
            patient_id=patient_id, source_doc="note", source_doc_id=doc_id,
            source_format="note_shorthand", method="regex", wound_index=idx,
            wound_type=N.normalize_wound_type(window) or N.normalize_wound_type(clean),
            stage=N.normalize_stage(window),
            location=N.find_location(window),
            laterality=N.normalize_laterality(window),
            length_cm=m.get("length_cm"),
            width_cm=m.get("width_cm"),
            depth_cm=m.get("depth_cm"),
            drainage_amount=N.normalize_drainage(window),
            drainage_type=N.normalize_drainage_type(window),
            confidence=0.6 if multi else 0.7,
            raw_span=window.strip()[:500],
        )
        if multi:
            ext._flag("multi_wound")
        if m.get("implausible"):
            ext._flag("implausible_measurement")
        results.append(ext)

    # primary = largest area (L*W), else first
    def area(e):
        return (e.length_cm or 0) * (e.width_cm or 0)
    if results:
        primary = max(results, key=area)
        for e in results:
            e.is_primary = e is primary
            e.finalize()
    return results


# --- dispatch -------------------------------------------------------------

def parse_document(doc):
    """doc: {'kind': 'note'|'assessment', 'patient_id', 'id', ...}."""
    pid = doc["patient_id"]
    did = doc["id"]
    if doc["kind"] == "assessment":
        shape, payload = detect_assessment(doc.get("raw_json"))
        if shape == "assessment_structured":
            return parse_structured_assessment(pid, did, payload)
        if shape == "assessment_narrative":
            return parse_envive(pid, did, "assessment_narrative", payload)
        ext = WoundExtraction(pid, "assessment", did, "unknown", "regex", confidence=0.0)
        ext._flag("unparseable")
        return [ext.finalize()]

    text = doc.get("note_text") or ""
    fmt = detect_note_format(text)
    if fmt == "note_envive":
        return parse_envive(pid, did, "note_envive", text)
    if fmt == "note_soap":
        return parse_soap(pid, did, text)
    return parse_shorthand(pid, did, text)
