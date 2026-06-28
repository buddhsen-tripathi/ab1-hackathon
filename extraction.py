"""
Wound field extraction from assessments (structured) and notes (regex).
Produces one row per patient with extracted wound fields.
"""

import re
import ast
import json
import pandas as pd

# ── Assessment extraction ─────────────────────────────────────────────────────

def parse_assessment_sections(raw: str) -> dict:
    """Parse raw_sections list-of-dicts into flat key->value."""
    try:
        sections = ast.literal_eval(raw) if isinstance(raw, str) else []
        flat = {}
        for sec in sections:
            for q in sec.get("questions", []):
                flat[q["question"]] = q.get("answer")
        return flat
    except Exception:
        return {}


def extract_from_assessment(row: pd.Series) -> dict:
    fields = parse_assessment_sections(row.get("raw_sections", ""))

    def val(key):
        v = fields.get(key)
        return None if (v is None or str(v).strip() in ("", "N/A", "None")) else str(v).strip()

    def num(key):
        v = val(key)
        try:
            return float(v) if v else None
        except ValueError:
            return None

    drainage_raw = val("Drainage Amount") or val("Drainage Present")
    drainage = normalize_drainage(drainage_raw)

    return {
        "src":        "assessment",
        "wound_type": val("Wound Type"),
        "stage":      val("Stage"),
        "location":   val("Location"),
        "length_cm":  num("Length (cm)"),
        "width_cm":   num("Width (cm)"),
        "depth_cm":   num("Depth (cm)"),
        "drainage":   drainage,
    }


# ── Note extraction (regex) ───────────────────────────────────────────────────

WOUND_TYPE_MAP = {
    r"pressure\s+ulcer":           "Pressure Ulcer",
    r"diabetic\s+(foot\s+)?ulcer": "Diabetic Foot Ulcer",
    r"diabetic\b.*\bfoot\b":       "Diabetic Foot Ulcer",
    r"venous\s+(stasis\s+)?ulcer": "Venous Ulcer",
    r"arterial\s+ulcer":           "Arterial Ulcer",
    r"abscess":                    "Abscess",
    r"burn":                       "Burn",
    r"surgical\s+site":            "Surgical Site Infection",
}

DRAINAGE_MAP = {
    r"\b(none|dry|no\s+drainage)\b":         "none",
    r"\b(min|minimal|light|slight|scant)\b": "light",
    r"\b(mod|moderate)\b":                   "moderate",
    r"\b(heavy|large|copious)\b":            "heavy",
}

STAGE_PATTERN = re.compile(
    r"stage[:\s]*(\d|i{1,3}v?|unstageable|N/A)",
    re.IGNORECASE,
)

# Envive format: "Wound Status: <type> to <location> / Measures L x W cm / Stage: X"
ENVIVE_PATTERN = re.compile(
    r"Wound Status:\s*(?P<wound_type>.+?)\s+to\s+(?P<location>.+?)\s*/"
    r"\s*Measures\s+(?P<length>[\d.]+)\s*cm\s*x\s*(?P<width>[\d.]+)\s*cm"
    r"(?:\s*/\s*Stage:\s*(?P<stage>[^\n/]+))?",
    re.IGNORECASE,
)

# Prose format: measurements like "5.9 x 4.5cm, depth 1.8cm"
PROSE_MEAS_PATTERN = re.compile(
    r"(?P<length>[\d.]+)\s*[xX]\s*(?P<width>[\d.]+)\s*(?:cm)?"
    r"(?:,?\s*depth\s+(?P<depth>[\d.]+)\s*cm)?",
)

DEPTH_PATTERN = re.compile(r"depth\s+([\d.]+)\s*cm", re.IGNORECASE)


def normalize_drainage(text) -> str:
    if not text:
        return None
    for pattern, level in DRAINAGE_MAP.items():
        if re.search(pattern, text, re.IGNORECASE):
            return level
    return None


def extract_wound_type(text):
    for pattern, label in WOUND_TYPE_MAP.items():
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return None


def extract_stage(text):
    m = STAGE_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    if raw.lower() in ("n/a", "na"):
        return None
    return f"Stage {raw}" if raw.isdigit() else raw.title()


def extract_from_note(note_text) -> dict:
    if not isinstance(note_text, str):
        return {}

    is_envive = "*Envive" in note_text

    wound_type = location = stage = None
    length = width = depth = drainage = None

    if is_envive:
        m = ENVIVE_PATTERN.search(note_text)
        if m:
            wound_type = extract_wound_type(m.group("wound_type"))
            location   = m.group("location").strip()
            length     = float(m.group("length"))
            width      = float(m.group("width"))
            stage_raw  = m.group("stage")
            if stage_raw and stage_raw.strip().lower() not in ("n/a", ""):
                stage = stage_raw.strip()
    else:
        # Prose / multi-wound: take first measurement block (primary wound)
        m = PROSE_MEAS_PATTERN.search(note_text)
        if m:
            length = float(m.group("length"))
            width  = float(m.group("width"))
            if m.group("depth"):
                depth = float(m.group("depth"))

        if depth is None:
            dm = DEPTH_PATTERN.search(note_text)
            if dm:
                depth = float(dm.group(1))

        wound_type = extract_wound_type(note_text)
        stage      = extract_stage(note_text)

        loc_m = re.search(
            r"(?:pressure\s+ulcer|diabetic|venous|arterial|abscess|burn)\s+"
            r"(?:foot\s+)?(?:ulcer\s+)?(?:to\s+)?([A-Za-z\s]+?)(?:\s+measures|\s+\d|,|$)",
            note_text, re.IGNORECASE
        )
        if loc_m:
            location = loc_m.group(1).strip()

    drain_m = re.search(
        r"[Dd]rainage[^.]*?[-:]?\s*([a-zA-Z\s,]+?)(?:\.|$|\n)",
        note_text
    )
    if drain_m:
        drainage = normalize_drainage(drain_m.group(1))

    if wound_type is None:
        wound_type = extract_wound_type(note_text)

    return {
        "src":        "note",
        "wound_type": wound_type,
        "stage":      stage,
        "location":   location,
        "length_cm":  length,
        "width_cm":   width,
        "depth_cm":   depth,
        "drainage":   drainage,
    }


# ── Merge: best data per patient ─────────────────────────────────────────────

def best_value(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def extract_all(assessments: pd.DataFrame, notes: pd.DataFrame) -> pd.DataFrame:
    # Assessment fields — one per patient
    assess_rows = {}
    for _, row in assessments.iterrows():
        pid = row["patient_id_str"]
        assess_rows[pid] = extract_from_assessment(row)

    # Note fields — most recent note per patient
    notes = notes.sort_values("effective_date", ascending=False)
    note_rows = {}
    for _, row in notes.iterrows():
        pid = row["patient_id_str"]
        if pid not in note_rows:
            note_rows[pid] = extract_from_note(row["note_text"])

    # Merge: assessment wins for structured fields, note fills gaps
    all_pids = set(assess_rows) | set(note_rows)
    records = []
    for pid in sorted(all_pids):
        a = assess_rows.get(pid, {})
        n = note_rows.get(pid, {})
        records.append({
            "patient_id": pid,
            "wound_type": best_value(a.get("wound_type"), n.get("wound_type")),
            "stage":      best_value(a.get("stage"), n.get("stage")),
            "location":   best_value(a.get("location"), n.get("location")),
            "length_cm":  best_value(a.get("length_cm"), n.get("length_cm")),
            "width_cm":   best_value(a.get("width_cm"), n.get("width_cm")),
            "depth_cm":   best_value(a.get("depth_cm"), n.get("depth_cm")),
            "drainage":   best_value(a.get("drainage"), n.get("drainage")),
            "data_source": "assessment+note" if (a and n) else ("assessment" if a else "note"),
        })

    return pd.DataFrame(records)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    assessments = pd.read_csv("data/assessments.csv")
    notes       = pd.read_csv("data/notes.csv")

    df = extract_all(assessments, notes)

    print("=== Extraction completeness ===")
    fields = ["wound_type", "stage", "location", "length_cm", "width_cm", "depth_cm", "drainage"]
    for f in fields:
        filled = df[f].notna().sum()
        print(f"  {f:12s}: {filled}/{len(df)} ({filled/len(df)*100:.0f}%)")

    print()
    print("=== Sample output (first 5) ===")
    print(df.head().to_string(index=False))

    df.to_csv("data/wound_extracted.csv", index=False)
    print(f"\nSaved {len(df)} rows → data/wound_extracted.csv")
