"""Cleaning + normalization helpers shared by every parser.

These collapse the messy real-world variants we observed (doubled words,
7 drainage adjectives, free-text wound types, depth stated separately) into
the controlled vocabularies in schema.py.
"""
import re

# --- abbreviation knowledge-base seam ------------------------------------
# Minimal inline map for now. The real KB (DB-backed, learned from data to
# reduce LLM latency) replaces this dict later without touching call sites.
ABBREVIATIONS = {
    r"\baprx\b": "approx",
    r"\bpt\b": "patient",
    r"\bw/\b": "with",
    r"\bs/p\b": "status post",
    r"\bmeas\b": "measures",
}


def expand_abbreviations(text: str) -> str:
    if not text:
        return text
    for pat, repl in ABBREVIATIONS.items():
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)
    return text


# --- text cleaning -------------------------------------------------------

_DOUBLED_RE = re.compile(r"\b(\w+)(\s+\1\b)+", re.IGNORECASE)


def dedupe_doubled_words(text: str):
    """Collapse 'Diabetic diabetic' -> 'Diabetic'. Returns (clean, had_double)."""
    if not text:
        return text, False
    had = bool(_DOUBLED_RE.search(text))
    return _DOUBLED_RE.sub(r"\1", text), had


def clean_text(text: str):
    """Returns (clean_text, had_doubled_word)."""
    if not text:
        return "", False
    t = expand_abbreviations(text)
    t, had = dedupe_doubled_words(t)
    t = re.sub(r"[ \t]+", " ", t)
    return t, had


# --- drainage: 7 clinical adjectives -> 4 required buckets ----------------

_DRAINAGE_MAP = {
    "none": "none", "no": "none", "dry": "none", "absent": "none",
    "scant": "light", "minimal": "light", "small": "light",
    "trace": "light", "slight": "light", "light": "light", "min": "light",
    "moderate": "moderate", "mod": "moderate",
    "large": "heavy", "heavy": "heavy", "copious": "heavy",
    "profuse": "heavy", "excessive": "heavy",
}
_DRAINAGE_RE = re.compile(
    r"\b(" + "|".join(sorted(_DRAINAGE_MAP, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def normalize_drainage(text: str):
    if not text:
        return None
    m = _DRAINAGE_RE.search(text)
    return _DRAINAGE_MAP[m.group(1).lower()] if m else None


_DRAINAGE_TYPE_RE = re.compile(
    r"\b(serosanguineous|serous|sanguineous|purulent|seropurulent)\b", re.IGNORECASE
)


def normalize_drainage_type(text: str):
    m = _DRAINAGE_TYPE_RE.search(text or "")
    return m.group(1).lower() if m else None


# --- wound type ----------------------------------------------------------

_WOUND_TYPE_PATTERNS = [
    (re.compile(r"pressure\s+(ulcer|injury|wound)|decubitus|\bpu\b", re.I), "pressure_ulcer"),
    (re.compile(r"diabetic|neuropathic|\bdfu\b", re.I), "diabetic_foot_ulcer"),
    (re.compile(r"venous|stasis|\bvlu\b", re.I), "venous_ulcer"),
    (re.compile(r"arterial|ischemic", re.I), "arterial_ulcer"),
    (re.compile(r"surgical|incision|\bssi\b|post[\s-]?op", re.I), "surgical_site_infection"),
    (re.compile(r"abscess", re.I), "abscess"),
    (re.compile(r"\bburn\b", re.I), "burn"),
]


def normalize_wound_type(text: str):
    if not text:
        return None
    for pat, canonical in _WOUND_TYPE_PATTERNS:
        if pat.search(text):
            return canonical
    return None


# --- stage ---------------------------------------------------------------

_STAGE_RE = re.compile(
    r"stage[:\s]*"
    r"(?:(unstageable|deep\s+tissue|dti)|(?:stage\s*)?([1-4]|i{1,3}v?|iv))",
    re.IGNORECASE,
)
_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4"}


def normalize_stage(text: str):
    """Returns canonical stage or None. 'N/A' -> None (expected for non-PU)."""
    if not text:
        return None
    m = _STAGE_RE.search(text)
    if not m:
        return None
    if m.group(1):
        word = m.group(1).lower()
        return "dti" if "tissue" in word or word == "dti" else "unstageable"
    val = m.group(2).lower()
    return _ROMAN.get(val, val)


# --- laterality ----------------------------------------------------------

_LAT_RE = re.compile(r"\b(left|right|bilateral|bilat)\b", re.IGNORECASE)
_LAT_ABBR_RE = re.compile(r"(?<![a-z])([lr])\s+(?=[a-z])", re.IGNORECASE)


def normalize_laterality(text: str):
    if not text:
        return None
    m = _LAT_RE.search(text)
    if m:
        v = m.group(1).lower()
        return "bilateral" if v.startswith("bilat") else v
    return None


# --- anatomical-site gazetteer (robust location extraction) ---------------
# Longest-first so "lower leg" wins over "leg", "sacral region" over "sacrum".
_BODY_SITES = sorted(
    [
        "sacral region", "sacrum", "coccyx", "ischial tuberosity", "ischium",
        "greater trochanter", "trochanter", "buttock", "gluteal", "hip",
        "heel", "plantar", "forefoot", "midfoot", "foot", "ankle",
        "lateral malleolus", "medial malleolus", "malleolus", "great toe",
        "toe", "lower leg", "upper leg", "calf", "shin", "thigh", "knee",
        "elbow", "forearm", "upper arm", "arm", "abdominal wall", "abdomen",
        "sacrococcygeal", "back", "shoulder", "scalp", "ear",
    ],
    key=len,
    reverse=True,
)
_SITE_RE = re.compile(
    r"\b(left|right|bilateral)?\s*(" + "|".join(_BODY_SITES) + r")\b",
    re.IGNORECASE,
)


def find_location(text: str):
    """Find a known anatomical site (with optional side) — far more reliable
    than slicing free text. Returns e.g. 'Left buttock', 'Sacral region'."""
    if not text:
        return None
    m = _SITE_RE.search(text)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(0)).strip().capitalize()


# --- measurements --------------------------------------------------------
# Matches "2.9 cm x 2.8 cm", "4.3 x 1.8 x 0.3 cm", "5.9 x 4.5cm",
# optionally followed by a separate depth phrase ("depth 1.8cm", "0.9cm deep").
_NUM = r"(\d+(?:\.\d+)?)"
_DIM_RE = re.compile(
    rf"{_NUM}\s*(?:cm)?\s*[x×]\s*{_NUM}\s*(?:cm)?"
    rf"(?:\s*[x×]\s*{_NUM}\s*(?:cm)?)?",
    re.IGNORECASE,
)
_DEPTH_NEAR_RE = re.compile(
    rf"(?:depth[:\s]*{_NUM}\s*cm|{_NUM}\s*cm\s*deep)", re.IGNORECASE
)

PLAUSIBLE_MAX_CM = 60.0
PLAUSIBLE_MIN_CM = 0.1


def find_measurements(text: str):
    """Return list of dicts {length_cm,width_cm,depth_cm,span,implausible}.

    One dict per measurement cluster found (supports multi-wound notes).
    Looks ~40 chars past a 2-D match for a separate depth phrase.
    """
    if not text:
        return []
    out = []
    for m in _DIM_RE.finditer(text):
        l, w, d = m.group(1), m.group(2), m.group(3)
        length = float(l)
        width = float(w)
        depth = float(d) if d else None
        if depth is None:
            tail = text[m.end():m.end() + 40]
            dm = _DEPTH_NEAR_RE.search(tail)
            if dm:
                depth = float(dm.group(1) or dm.group(2))
        vals = [v for v in (length, width, depth) if v is not None]
        implausible = any(v < PLAUSIBLE_MIN_CM or v > PLAUSIBLE_MAX_CM for v in vals)
        out.append(
            {
                "length_cm": length,
                "width_cm": width,
                "depth_cm": depth,
                "span": m.group(0),
                "implausible": implausible,
            }
        )
    return out


def to_float(val):
    try:
        return float(str(val).strip())
    except (TypeError, ValueError):
        return None
