"""Routing decision tree → one EligibilityResult per patient.

Cascade (thresholds from the liliia blueprint + our conflict gate):
  1. no active MCB                          -> reject
  2. no wound at all                        -> reject
  3. incomplete & confidence >= 0.4         -> flag_for_review (list missing)
  4. incomplete & confidence < 0.4          -> reject (unreliable)
  5. complete & blocking flag (conflict /   -> flag_for_review (discrepancy)
     multi-wound / implausible)
  6. complete & confidence >= 0.75          -> auto_accept
  7. complete & confidence < 0.75           -> flag_for_review (low confidence)
"""
from .coverage import has_active_mcb
from .fusion import missing_fields, reconcile
from .models import FIELD_LABELS, EligibilityResult

AUTO_ACCEPT_CONF = 0.75
MIN_REVIEW_CONF = 0.4


def _is_blocking(flag):
    return "conflict" in flag or flag in ("multi_wound", "implausible_measurement")


def _labels(items):
    return ", ".join(FIELD_LABELS.get(i, i) for i in items)


def _summary(w):
    parts = []
    if w.get("wound_type"):
        stage = f" stage {w['stage']}" if w.get("stage") else ""
        parts.append(f"{w['wound_type']}{stage}")
    if w.get("location"):
        parts.append(f"at {w['location']}")
    dims = [f"{lbl} {w[f]}" for f, lbl in
            (("length_cm", "L"), ("width_cm", "W"), ("depth_cm", "D"))
            if w.get(f) is not None]
    if dims:
        parts.append(" × ".join(dims) + " cm")
    if w.get("drainage_amount"):
        parts.append(f"{w['drainage_amount']} drainage")
    return ", ".join(parts) if parts else "no structured wound details"


def _decide(mcb, wound, has_wound_dx):
    """Return (decision, reason, missing_fields)."""
    # Gate 1 — payer
    if not mcb:
        return ("reject",
                "No active Medicare Part B coverage — not eligible for Part B "
                "wound-care billing.", ["medicare_part_b"])

    # Gate 2 — supporting ICD-10 wound diagnosis (claims are denied without one)
    if not has_wound_dx:
        if wound and wound.get("wound_type"):
            return ("flag_for_review",
                    "Wound documented in notes/assessments but no active wound "
                    "ICD-10 diagnosis on record — Medicare denies claims without a "
                    "diagnosis code. Clinician must add the wound diagnosis before "
                    "billing.", ["wound_diagnosis"])
        return ("reject",
                "Active Medicare Part B but no wound diagnosis and no wound "
                "documentation.", ["wound_diagnosis"])

    # Gate 3 — extraction completeness + confidence
    if wound is None:
        return ("flag_for_review",
                "Active Medicare Part B and an active wound diagnosis on record, "
                "but no wound measurements found in notes or assessments.",
                ["wound_documentation"])

    miss = missing_fields(wound)
    conf = wound.get("confidence") or 0.0
    blocking = [f for f in (wound.get("flags") or []) if _is_blocking(f)]

    if miss:
        if conf >= MIN_REVIEW_CONF:
            return ("flag_for_review",
                    f"Active Medicare Part B. Incomplete wound documentation — "
                    f"missing {_labels(miss)}. Found: {_summary(wound)}. Obtain "
                    f"the missing fields before billing.", miss)
        return ("reject",
                "Active Medicare Part B, but wound data could not be reliably "
                "extracted. Obtain a structured wound assessment before routing.",
                miss)

    if blocking:
        return ("flag_for_review",
                f"Active Medicare Part B with all fields present ({_summary(wound)}), "
                f"but flagged: {_labels(blocking)}. Clinician should verify before "
                f"billing.", [])

    if conf >= AUTO_ACCEPT_CONF:
        return ("auto_accept",
                f"Active Medicare Part B. All required wound fields documented "
                f"({_summary(wound)}). Source: {wound.get('source')}. Safe to route "
                f"to billing.", [])

    return ("flag_for_review",
            f"Active Medicare Part B. All fields present ({_summary(wound)}) but "
            f"extraction confidence is low ({conf:.0%}). Clinician should verify.", [])


def route(meta, coverage_records, candidates, has_wound_dx=False):
    mcb = has_active_mcb(coverage_records)
    wound = reconcile(candidates)
    decision, reason, missing = _decide(mcb, wound, has_wound_dx)
    w = wound or {}
    return EligibilityResult(
        internal_id=meta["internal_id"],
        patient_id=meta["patient_id"],
        facility_id=meta["facility_id"],
        first_name=meta.get("first_name"),
        last_name=meta.get("last_name"),
        is_new_admission=bool(meta.get("is_new_admission")),
        has_active_mcb=mcb,
        submission_eligible=mcb,
        wound_type=w.get("wound_type"),
        stage=w.get("stage"),
        location=w.get("location"),
        laterality=w.get("laterality"),
        length_cm=w.get("length_cm"),
        width_cm=w.get("width_cm"),
        depth_cm=w.get("depth_cm"),
        area_cm2=w.get("area_cm2"),
        drainage_amount=w.get("drainage_amount"),
        extraction_source=w.get("source") or "none",
        extraction_confidence=round(w.get("confidence") or 0.0, 2),
        routing_decision=decision,
        reason=reason,
        missing_fields=missing,
        flags=w.get("flags") or [],
        secondary_wound_count=meta.get("secondary_wound_count", 0),
    )
