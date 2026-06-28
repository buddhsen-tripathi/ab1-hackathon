"""Cross-source reconciliation.

Each patient has up to a few primary wound extractions (one per note +
assessment). We pick the best, then merge the top two to FILL GAPS — e.g. an
Envive note (no depth) + a structured assessment (has depth) becomes complete.

Our addition over the liliia blueprint: when two sources both state a field and
DISAGREE, we don't silently merge — we record a *_conflict flag so routing can
send it to review.
"""
from .models import required_fields

_TEXT_FIELDS = ("wound_type", "stage", "location", "laterality",
                "drainage_amount", "drainage_type")
_NUM_FIELDS = ("length_cm", "width_cm", "depth_cm")


def missing_fields(w):
    # Required set depends on wound type (depth optional for venous, etc.).
    return [f for f in required_fields(w.get("wound_type")) if w.get(f) in (None, "")]


def is_complete(w):
    return not missing_fields(w)


def _score(w):
    return (is_complete(w), w.get("confidence") or 0.0, w.get("length_cm") is not None)


def _detect_conflicts(a, b):
    flags = []
    if a.get("wound_type") and b.get("wound_type") and a["wound_type"] != b["wound_type"]:
        flags.append("wound_type_conflict")
    if a.get("laterality") and b.get("laterality") and a["laterality"] != b["laterality"]:
        flags.append("laterality_conflict")
    if a.get("drainage_amount") and b.get("drainage_amount") and a["drainage_amount"] != b["drainage_amount"]:
        flags.append("drainage_conflict")
    for f in _NUM_FIELDS:
        av, bv = a.get(f), b.get(f)
        if av is not None and bv is not None and abs(av - bv) > max(0.5, 0.2 * max(av, bv)):
            flags.append("measurement_conflict")
            break
    return flags


def _merge(primary, secondary):
    """primary = higher-confidence source; secondary only fills gaps."""
    conflicts = _detect_conflicts(primary, secondary)
    fused = {}
    for f in _TEXT_FIELDS:
        fused[f] = primary.get(f) or secondary.get(f)
    for f in _NUM_FIELDS:
        fused[f] = primary.get(f) if primary.get(f) is not None else secondary.get(f)
    fused["area_cm2"] = (
        round(fused["length_cm"] * fused["width_cm"], 2)
        if fused.get("length_cm") and fused.get("width_cm")
        else None
    )

    src = primary.get("source_format")
    if secondary.get("source_format") and secondary["source_format"] != src:
        src = f"{src}+{secondary['source_format']}"
    fused["source"] = src

    # carry the winning source's own flags, plus any cross-source conflicts
    flags = list(primary.get("flags") or [])
    for c in conflicts:
        if c not in flags:
            flags.append(c)
    fused["flags"] = flags

    conf = max(primary.get("confidence") or 0.0, secondary.get("confidence") or 0.0)
    if is_complete(fused) and not conflicts:
        conf = max(conf, 0.85)   # corroborated + complete -> high confidence
    fused["confidence"] = conf
    return fused


def reconcile(candidates):
    """Return one fused wound dict (or None) from a patient's primary extractions."""
    cands = [c for c in (candidates or []) if c]
    if not cands:
        return None
    cands = sorted(cands, key=_score, reverse=True)
    best = cands[0]
    if len(cands) >= 2:
        merged = _merge(best, cands[1])
        if is_complete(merged) or (merged["confidence"] >= (best.get("confidence") or 0.0)):
            return merged
    return _merge(best, best)  # normalize single source (no conflicts vs self)
