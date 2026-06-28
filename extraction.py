"""
Wound field extraction from assessments (structured/narrative) and notes
(SOAP, prose, multi-wound, free-text narrative).

Source-specific confidence scores per the routing spec:
  assessment_structured  → 0.98 (machine-generated, trusted)
  assessment_narrative   → 0.85 × (fields_found/5), floor 0.88 if complete
  note_soap              → 0.95 if fields_found >= 4, else 0.75 × (fields_found/5)
  note_prose             → 0.90 if complete, else 0.75 × (fields_found/5)
  note_multi             → 0.65 × (fields_found/5)
  note_text              → 0.60 × (fields_found/5), floor 0.80 if complete

Fusion: if two sources available, merge (primary = higher confidence, fill gaps
from secondary). If merged result is complete: confidence = max(merged, 0.85).
"""
from __future__ import annotations

import ast
import re

import pandas as pd

from models import WoundExtraction


# ── Shared patterns ───────────────────────────────────────────────────────────

WOUND_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"pressure\s+ulcer",            "pressure ulcer"),
    (r"diabetic\s+foot\s+ulcer",     "diabetic foot ulcer"),
    (r"venous\s+stasis\s+ulcer",     "venous stasis ulcer"),
    (r"venous\s+ulcer",              "venous ulcer"),
    (r"arterial\s+ulcer",            "arterial ulcer"),
    (r"surgical\s+site\s+infection", "surgical site infection"),
    (r"\babscess\b",                 "abscess"),
    (r"\bburn\b",                    "burn"),
]

_DRAINAGE_MAP: dict[str, tuple[str, ...]] = {
    "none":     ("none", "no drainage", "dry", "no drain"),
    "light":    ("light", "minimal", "scant", "min"),
    "moderate": ("moderate", "mod"),
    "heavy":    ("heavy", "large", "copious"),
}

STAGE_PATTERN = re.compile(
    r"stage\s*(?:[:.]?\s*)?(?:stage\s*)?(\d+|unstageable)",
    re.IGNORECASE,
)
LABELED_DIMS = re.compile(
    r"Length:\s*([\d.]+)\s*cm.*?Width:\s*([\d.]+)\s*cm(?:.*?Depth:\s*([\d.]+)\s*cm)?",
    re.IGNORECASE | re.DOTALL,
)
MEASURES_PATTERN = re.compile(
    r"(?:Measures|Meas\.?)\s*([\d.]+)\s*(?:cm\s*)?[x×]\s*([\d.]+)\s*(?:cm\s*)?"
    r"(?:[x×]\s*([\d.]+)\s*(?:cm)?)?",
    re.IGNORECASE,
)
LOOSE_DIMS = re.compile(
    r"([\d.]+)\s*(?:cm\s*)?[x×]\s*([\d.]+)\s*(?:cm\s*)?[x×]\s*([\d.]+)\s*cm",
    re.IGNORECASE,
)
DRAINAGE_LABEL = re.compile(
    r"Drainage(?:\s+(?:Amount|Present))?\s*[:\-]\s*([^.\n]+)",
    re.IGNORECASE,
)
PROSE_MEAS = re.compile(
    r"Meas\.?\s*([\d.]+)\s*[x×]\s*([\d.]+)\s*(?:[x×]\s*([\d.]+))?\s*cm",
    re.IGNORECASE,
)
APRX_MEAS = re.compile(
    r"measures?\s+aprx\.?\s*([\d.]+)\s*[x×]\s*([\d.]+)\s*cm",
    re.IGNORECASE,
)
SEPARATE_DEPTH = re.compile(
    r"(?:,\s*)?depth\s+([\d.]+)\s*cm|([\d.]+)\s*cm\s+deep",
    re.IGNORECASE,
)
MULTI_MARKERS = re.compile(
    r"(?:pressure\s+ulcer|diabetic|venous|arterial|surgical|abscess|burn|"
    r"wound|heel\s+wound|Wound\s+note)",
    re.IGNORECASE,
)
MULTI_SPLITTERS = re.compile(
    r"(?:also\s+eval|second\s+wound|wound\s+also|additional\s+wound|"
    r"secondarily|other\s+wound)",
    re.IGNORECASE,
)


# ── Low-level text helpers ────────────────────────────────────────────────────

def normalize_drainage(text: str | None) -> str | None:
    if not text:
        return None
    lower = text.lower()
    for level, keywords in _DRAINAGE_MAP.items():
        if any(kw in lower for kw in keywords):
            return level
    return None


def extract_wound_type(text: str) -> str | None:
    # Envive: "Wound Status: <type> to <location>"
    m = re.search(r"Wound Status:\s*([A-Za-z\s]+?)\s+to\s+", text, re.IGNORECASE)
    if m:
        key = m.group(1).strip().lower()
        for pat, label in WOUND_TYPE_PATTERNS:
            if re.search(pat, key):
                return label
    for pat, label in WOUND_TYPE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return label
    return None


def extract_stage(text: str) -> str | None:
    m = STAGE_PATTERN.search(text)
    if not m:
        return None
    val = m.group(1).lower()
    return "Unstageable" if val == "unstageable" else f"Stage {val}"


def extract_location(text: str) -> str | None:
    m = re.search(r"Location:\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"Wound Status:[^/]*?\sto\s+([^/\n]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(
        r"(?:pressure\s+ulcer|diabetic|venous|arterial|wound)\s+to\s+([^/\n,]+)",
        text, re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return None


def extract_measurements(text: str) -> tuple[float | None, float | None, float | None]:
    m = LABELED_DIMS.search(text)
    if m:
        return float(m.group(1)), float(m.group(2)), (float(m.group(3)) if m.group(3) else None)
    m = MEASURES_PATTERN.search(text)
    if m:
        return float(m.group(1)), float(m.group(2)), (float(m.group(3)) if m.group(3) else None)
    m = LOOSE_DIMS.search(text)
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    return None, None, None


def extract_drainage(text: str) -> str | None:
    m = DRAINAGE_LABEL.search(text)
    if m:
        return normalize_drainage(m.group(1))
    m = re.search(r"/\s*Drainage:\s*([^/\n]+)", text, re.IGNORECASE)
    if m:
        return normalize_drainage(m.group(1))
    m = re.search(
        r"drainage(?:\s+present)?[^.\n]*?(none|light|moderate|heavy)",
        text, re.IGNORECASE,
    )
    if m:
        return normalize_drainage(m.group(1))
    return None


def _fields_found(*vals: object) -> int:
    return sum(1 for v in vals if v is not None)


def _collect_evidence(text: str, wound: WoundExtraction) -> dict[str, str]:
    ev: dict[str, str] = dict(wound.evidence)
    for field_name, value in [
        ("wound_type", wound.wound_type),
        ("location",   wound.location),
        ("stage",      wound.stage),
        ("drainage",   wound.drainage_amount),
    ]:
        if not value or field_name in ev:
            continue
        idx = text.lower().find(str(value).lower())
        if idx >= 0:
            ev[field_name] = text[idx: idx + len(str(value))]
    if wound.length_cm is not None and wound.width_cm is not None:
        m = re.search(
            rf"{wound.length_cm}\s*[x×]\s*{wound.width_cm}", text, re.IGNORECASE
        )
        if m:
            ev["measurements"] = m.group(0)
    return ev


def _to_float(v: object) -> float | None:
    try:
        return float(v) if v is not None else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


# ── Assessment extraction ─────────────────────────────────────────────────────

_SECTION_FIELD_MAP = {
    "Wound Type":      "wound_type",
    "Stage":           "stage",
    "Location":        "location",
    "Length (cm)":     "length_cm",
    "Width (cm)":      "width_cm",
    "Depth (cm)":      "depth_cm",
    "Drainage Amount": "drainage_amount",
    "Drainage Present": "_drainage_present",
}


def _parse_raw_sections(raw: str) -> tuple[dict[str, str | None], list[str]]:
    """Parse raw_sections Python literal into (flat_fields, narrative_texts)."""
    try:
        sections = ast.literal_eval(raw) if isinstance(raw, str) else []
    except Exception:
        return {}, []

    flat: dict[str, str | None] = {}
    narratives: list[str] = []
    for sec in sections:
        for q in sec.get("questions", []):
            question = q.get("question", "")
            answer = q.get("answer")
            if answer is None or str(answer).strip() in ("", "N/A", "None"):
                continue
            answer_str = str(answer).strip()
            if question in _SECTION_FIELD_MAP:
                flat[_SECTION_FIELD_MAP[question]] = answer_str
            elif isinstance(answer, str) and len(answer_str) > 40:
                narratives.append(answer_str)
    return flat, narratives


def _flat_to_structured(flat: dict[str, str | None]) -> WoundExtraction:
    wt_raw = flat.get("wound_type")
    wound_type = wt_raw.lower() if wt_raw else None

    stage = flat.get("stage")
    if stage and stage.lower() in ("n/a", "na", "none", ""):
        stage = None

    drainage_raw = flat.get("drainage_amount") or flat.get("_drainage_present")
    drainage = normalize_drainage(drainage_raw) if drainage_raw else None

    return WoundExtraction(
        wound_type=wound_type,
        stage=stage,
        location=flat.get("location"),
        length_cm=_to_float(flat.get("length_cm")),
        width_cm=_to_float(flat.get("width_cm")),
        depth_cm=_to_float(flat.get("depth_cm")),
        drainage_amount=drainage,
        source="assessment_structured",
        confidence=0.98,
    )


def _parse_narrative(text: str) -> WoundExtraction:
    wound_type = extract_wound_type(text)
    stage      = extract_stage(text)
    location   = extract_location(text)
    length, width, depth = extract_measurements(text)
    drainage   = extract_drainage(text)

    found = _fields_found(wound_type, length, width, depth, drainage)
    is_complete = all(v is not None for v in (wound_type, length, width, depth, drainage))
    confidence = 0.85 * (found / 5)
    if is_complete:
        confidence = max(confidence, 0.88)

    return WoundExtraction(
        wound_type=wound_type,
        stage=stage,
        location=location,
        length_cm=length,
        width_cm=width,
        depth_cm=depth,
        drainage_amount=drainage,
        source="assessment_narrative",
        confidence=round(confidence, 2),
        raw_snippet=text[:200],
    )


def parse_assessment_row(raw_sections: str | None) -> WoundExtraction | None:
    if not raw_sections or (isinstance(raw_sections, float)):
        return None
    raw = str(raw_sections)
    flat, narratives = _parse_raw_sections(raw)

    has_structured = bool(flat.get("length_cm") or flat.get("wound_type"))
    if has_structured:
        structured = _flat_to_structured(flat)
        if narratives:
            best_narr = max((_parse_narrative(n) for n in narratives), key=lambda w: w.confidence)
            return _merge(structured, best_narr)
        return structured

    if narratives:
        candidates = [_parse_narrative(n) for n in narratives]
        return max(candidates, key=lambda w: w.confidence)

    return None


# ── Note extraction ───────────────────────────────────────────────────────────

def _is_soap_note(text: str) -> bool:
    return bool(
        re.search(r"Location:\s", text, re.IGNORECASE)
        and re.search(r"(?:Length:|Wound Type:)", text, re.IGNORECASE)
    )


def _is_prose_note(text: str) -> bool:
    return bool(
        re.search(r"Meas\.?\s*\d", text, re.IGNORECASE)
        or re.search(r"measures?\s+aprx", text, re.IGNORECASE)
        or re.search(r"Wound note\s*-", text, re.IGNORECASE)
    )


def _is_multi_wound_note(text: str) -> bool:
    if MULTI_SPLITTERS.search(text):
        return True
    sentences = re.split(r"(?<=\.)\s+", text)
    return sum(1 for s in sentences if MULTI_MARKERS.search(s)) >= 3


def _parse_soap_note(text: str) -> WoundExtraction:
    wt_m = re.search(r"Wound Type:\s*([^\n]+)", text, re.IGNORECASE)
    wound_type = stage = None
    if wt_m:
        wt_line = wt_m.group(1).strip()
        wound_type = extract_wound_type(wt_line) or wt_line.split(",")[0].strip().lower()
        stage = extract_stage(wt_line)
    if not stage:
        stage = extract_stage(text)
    if not wound_type:
        wound_type = extract_wound_type(text)

    location = extract_location(text)
    length, width, depth = extract_measurements(text)
    dr_m = re.search(r"Drainage:\s*([^\n]+)", text, re.IGNORECASE)
    drainage = normalize_drainage(dr_m.group(1)) if dr_m else extract_drainage(text)

    found = _fields_found(wound_type, length, width, depth, drainage)
    confidence = 0.95 if found >= 4 else 0.75 * (found / 5)

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


def _parse_prose_note(text: str) -> WoundExtraction:
    wound_type = extract_wound_type(text)
    stage      = extract_stage(text)
    location   = extract_location(text)

    length = width = depth = None
    m = PROSE_MEAS.search(text)
    if m:
        length, width = float(m.group(1)), float(m.group(2))
        depth = float(m.group(3)) if m.group(3) else None
    else:
        m = APRX_MEAS.search(text)
        if m:
            length, width = float(m.group(1)), float(m.group(2))

    if depth is None and length is not None:
        dm = SEPARATE_DEPTH.search(text)
        if dm:
            depth = float(dm.group(1) or dm.group(2))

    if length is None:
        length, width, depth = extract_measurements(text)

    drainage = extract_drainage(text)

    found = _fields_found(wound_type, length, width, depth, drainage)
    is_complete = all(v is not None for v in (wound_type, length, width, depth, drainage))
    confidence = 0.90 if is_complete else 0.75 * (found / 5)

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
    )


def _parse_text_note(text: str) -> WoundExtraction:
    wound_type = extract_wound_type(text)
    stage      = extract_stage(text)
    location   = extract_location(text)
    length, width, depth = extract_measurements(text)
    drainage   = extract_drainage(text)

    found = _fields_found(wound_type, length, width, depth, drainage)
    is_complete = all(v is not None for v in (wound_type, length, width, depth, drainage))
    confidence = 0.60 * (found / 5)
    if is_complete:
        confidence = max(confidence, 0.80)

    return WoundExtraction(
        wound_type=wound_type,
        stage=stage,
        location=location,
        length_cm=length,
        width_cm=width,
        depth_cm=depth,
        drainage_amount=drainage,
        source="note_text",
        confidence=round(confidence, 2),
        raw_snippet=text[:300],
    )


def _parse_multi_wound_note(text: str) -> WoundExtraction:
    parts = MULTI_SPLITTERS.split(text)
    if len(parts) <= 1:
        parts = re.split(r"(?<=\.)\s+", text)

    segments = [
        s.strip() for s in parts
        if MULTI_MARKERS.search(s) and len(s.strip()) > 20
    ]
    if not segments:
        segments = [text]

    candidates: list[WoundExtraction] = []
    for seg in segments:
        w = _parse_prose_note(seg) if _is_prose_note(seg) else _parse_text_note(seg)
        w.source = "note_multi"
        candidates.append(w)

    def _score(w: WoundExtraction) -> float:
        base = w.confidence + (10.0 if w.is_complete() else 0.0)
        if w.length_cm and w.width_cm:
            base += w.length_cm * w.width_cm * 0.01
        return base

    primary = max(candidates, key=_score)
    primary.source = "note_multi"
    if len(candidates) > 1:
        primary.evidence["multi_wound"] = f"Primary of {len(candidates)} wounds"
    return primary


def _parse_note(text: str) -> WoundExtraction:
    if _is_soap_note(text):
        w = _parse_soap_note(text)
    elif _is_multi_wound_note(text):
        w = _parse_multi_wound_note(text)
    elif _is_prose_note(text):
        w = _parse_prose_note(text)
    else:
        w = _parse_text_note(text)
    w.evidence = _collect_evidence(text, w)
    return w


# ── Fusion ────────────────────────────────────────────────────────────────────

def _merge(a: WoundExtraction, b: WoundExtraction) -> WoundExtraction:
    """Merge two extractions — primary = higher confidence, fill gaps from secondary."""
    primary, secondary = (a, b) if a.confidence >= b.confidence else (b, a)
    evidence = {**secondary.evidence, **primary.evidence}
    merged = WoundExtraction(
        wound_type=primary.wound_type or secondary.wound_type,
        stage=primary.stage or secondary.stage,
        location=primary.location or secondary.location,
        length_cm=primary.length_cm if primary.length_cm is not None else secondary.length_cm,
        width_cm=primary.width_cm if primary.width_cm is not None else secondary.width_cm,
        depth_cm=primary.depth_cm if primary.depth_cm is not None else secondary.depth_cm,
        drainage_amount=primary.drainage_amount or secondary.drainage_amount,
        source=(
            f"{primary.source}+{secondary.source}"
            if primary.source != secondary.source
            else primary.source
        ),
        confidence=max(primary.confidence, secondary.confidence),
        raw_snippet=primary.raw_snippet or secondary.raw_snippet,
        evidence=evidence,
    )
    if merged.is_complete():
        merged.confidence = max(merged.confidence, 0.85)
    return merged


def extract_patient_wound(
    pat_assessments: pd.DataFrame,
    pat_notes: pd.DataFrame,
) -> WoundExtraction | None:
    candidates: list[WoundExtraction] = []

    for _, row in pat_assessments.iterrows():
        w = parse_assessment_row(row.get("raw_sections"))
        if w:
            candidates.append(w)

    pat_notes_sorted = pat_notes.sort_values("effective_date", ascending=False)
    for _, row in pat_notes_sorted.iterrows():
        text = row.get("note_text", "")
        if isinstance(text, str) and text.strip():
            candidates.append(_parse_note(text))

    if not candidates:
        return None

    sorted_cands = sorted(
        candidates,
        key=lambda w: (w.is_complete(), w.confidence),
        reverse=True,
    )

    if len(sorted_cands) >= 2:
        merged = _merge(sorted_cands[0], sorted_cands[1])
        if merged.confidence >= sorted_cands[0].confidence or merged.is_complete():
            return merged

    best = sorted_cands[0]
    if best.is_complete():
        best.confidence = max(best.confidence, 0.80)
    return best


# ── Legacy DataFrame API (keeps fetch_all.py / dashboard compatible) ──────────

def extract_all(assessments: pd.DataFrame, notes: pd.DataFrame) -> pd.DataFrame:
    all_pids: set[str] = set()
    if "patient_id_str" in assessments.columns:
        all_pids |= set(assessments["patient_id_str"].dropna())
    if "patient_id_str" in notes.columns:
        all_pids |= set(notes["patient_id_str"].dropna())

    records = []
    for pid in sorted(all_pids):
        pat_ass = (
            assessments[assessments["patient_id_str"] == pid]
            if "patient_id_str" in assessments.columns
            else assessments.iloc[0:0]
        )
        pat_n = (
            notes[notes["patient_id_str"] == pid]
            if "patient_id_str" in notes.columns
            else notes.iloc[0:0]
        )
        w = extract_patient_wound(pat_ass, pat_n)
        records.append({
            "patient_id":  pid,
            "wound_type":  w.wound_type if w else None,
            "stage":       w.stage if w else None,
            "location":    w.location if w else None,
            "length_cm":   w.length_cm if w else None,
            "width_cm":    w.width_cm if w else None,
            "depth_cm":    w.depth_cm if w else None,
            "drainage":    w.drainage_amount if w else None,
            "data_source": w.source if w else None,
            "confidence":  w.confidence if w else None,
        })

    return pd.DataFrame(records)


# ── Standalone run ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    assessments_df = pd.read_csv("data/assessments.csv")
    notes_df       = pd.read_csv("data/notes.csv")
    df = extract_all(assessments_df, notes_df)

    print("=== Extraction completeness ===")
    for f in ["wound_type", "stage", "location", "length_cm", "width_cm", "depth_cm", "drainage"]:
        filled = df[f].notna().sum()
        print(f"  {f:15s}: {filled}/{len(df)} ({filled / len(df) * 100:.0f}%)")

    print()
    print(df.head().to_string(index=False))
    df.to_csv("data/wound_extracted.csv", index=False)
    print(f"\nSaved {len(df)} rows → data/wound_extracted.csv")
