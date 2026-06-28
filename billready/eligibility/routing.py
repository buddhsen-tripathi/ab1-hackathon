from __future__ import annotations

from billready.models import EligibilityResult, PatientRecord, RoutingDecision, WoundExtraction
from billready.eligibility.coverage import has_active_mcb
from billready.extraction.fusion import extract_patient_wound

ALL_WOUND_FIELDS = [
    "wound_type",
    "length_cm",
    "width_cm",
    "depth_cm",
    "drainage_amount",
]

FIELD_LABELS = {
    "wound_type": "Wound type",
    "length_cm": "Length",
    "width_cm": "Width",
    "depth_cm": "Depth",
    "drainage_amount": "Drainage",
    "medicare_part_b": "Medicare Part B coverage",
    "wound_documentation": "Wound documentation",
}


def route_patient(record: PatientRecord) -> EligibilityResult:
    mcb_active = has_active_mcb(record.coverage)
    wound = extract_patient_wound(record)
    missing = _compute_missing(mcb_active, wound)

    decision, reason = _determine_routing(mcb_active, wound, missing)

    return EligibilityResult(
        internal_id=record.internal_id,
        patient_id=record.patient_id,
        facility_id=record.facility_id,
        first_name=record.first_name,
        last_name=record.last_name,
        is_new_admission=record.is_new_admission,
        has_active_mcb=mcb_active,
        submission_eligible=mcb_active,
        wound_type=wound.wound_type if wound else None,
        stage=wound.stage if wound else None,
        location=wound.location if wound else None,
        length_cm=wound.length_cm if wound else None,
        width_cm=wound.width_cm if wound else None,
        depth_cm=wound.depth_cm if wound else None,
        drainage_amount=wound.drainage_amount if wound else None,
        extraction_source=wound.source if wound else "none",
        extraction_confidence=wound.confidence if wound else 0.0,
        routing_decision=decision,
        reason=reason,
        missing_fields=missing,
    )


def _compute_missing(mcb_active: bool, wound: WoundExtraction | None) -> list[str]:
    missing: list[str] = []
    if not mcb_active:
        missing.append("medicare_part_b")
    if wound is None:
        if mcb_active:
            missing.append("wound_documentation")
        return missing
    missing.extend(wound.missing_fields())
    return missing


def _determine_routing(
    mcb_active: bool,
    wound: WoundExtraction | None,
    missing: list[str],
) -> tuple[RoutingDecision, str]:
    if not mcb_active:
        return (
            "reject",
            "Patient does not have active Medicare Part B coverage — not eligible for Part B wound care billing.",
        )

    if wound is None:
        return (
            "reject",
            "No wound documentation found in progress notes or assessments — cannot route to billing.",
        )

    wound_missing = [f for f in missing if f in ALL_WOUND_FIELDS]

    if not wound_missing and wound.confidence >= 0.75:
        summary = _wound_summary(wound)
        return (
            "auto_accept",
            f"Active Medicare Part B. All required wound fields documented ({summary}). "
            f"Source: {wound.source}. Safe to route to billing.",
        )

    if not wound_missing and wound.confidence < 0.75:
        summary = _wound_summary(wound)
        return (
            "flag_for_review",
            f"Active Medicare Part B. All wound fields present ({summary}) but extraction confidence "
            f"is low ({wound.confidence:.0%}). Clinician should verify before billing.",
        )

    if wound_missing and wound.confidence >= 0.4:
        missing_str = ", ".join(FIELD_LABELS.get(f, f) for f in wound_missing)
        found = _wound_summary(wound) if wound.wound_type or wound.length_cm else "partial data only"
        return (
            "flag_for_review",
            f"Active Medicare Part B. Incomplete wound documentation — missing: {missing_str}. "
            f"Found: {found}. Review chart and obtain missing fields before billing.",
        )

    return (
        "reject",
        "Active Medicare Part B but wound data could not be reliably extracted from available notes. "
        "Obtain structured wound assessment before routing to billing.",
    )


def _wound_summary(wound: WoundExtraction) -> str:
    parts = []
    if wound.wound_type:
        stage_part = f" stage {wound.stage}" if wound.stage else ""
        parts.append(f"{wound.wound_type}{stage_part}")
    if wound.location:
        parts.append(f"at {wound.location}")
    dims = []
    if wound.length_cm is not None:
        dims.append(f"L {wound.length_cm}")
    if wound.width_cm is not None:
        dims.append(f"W {wound.width_cm}")
    if wound.depth_cm is not None:
        dims.append(f"D {wound.depth_cm}")
    if dims:
        parts.append(" × ".join(dims) + " cm")
    if wound.drainage_amount:
        parts.append(f"{wound.drainage_amount} drainage")
    return ", ".join(parts) if parts else "no structured wound details"
