"""
Claim Readiness Scoring engine.

Score breakdown (max 100):
  Medicare Part B active:           +30
  Active wound type found:          +20
  Stage documented (pressure ulcer): +10
  Length documented:                +10
  Width documented:                 +10
  Depth documented:                 +10
  Drainage documented:              +10
  High confidence bonus (>0.85):    +10
  Ambiguity/conflict penalty:       -15

Routing:
  90-100 → auto_accept
  50-89  → flag_for_review
  0-49   → reject
"""
from typing import Optional

PRESSURE_ULCER_TYPES = {"pressure_ulcer", "Pressure Ulcer"}

SCORE_COMPONENTS = {
    "medicare_part_b": ("Medicare Part B active", 30),
    "wound_type": ("Active wound type found", 20),
    "stage": ("Stage documented (pressure ulcer)", 10),
    "length": ("Length documented", 10),
    "width": ("Width documented", 10),
    "depth": ("Depth documented", 10),
    "drainage": ("Drainage documented", 10),
    "confidence_bonus": ("High extraction confidence (>85%)", 10),
    "ambiguity_penalty": ("Ambiguity or data conflict detected", -15),
}


def compute_claim_score(patient_data: dict) -> dict:
    """
    Compute claim readiness score and return full breakdown.
    """
    score = 0
    breakdown = {}
    missing_fields = []
    is_pressure_ulcer = patient_data.get("wound_type") in PRESSURE_ULCER_TYPES

    # Medicare Part B
    if patient_data.get("has_medicare_part_b"):
        score += 30
        breakdown["medicare_part_b"] = {"label": "Medicare Part B active", "points": 30, "earned": True}
    else:
        breakdown["medicare_part_b"] = {"label": "Medicare Part B active", "points": 30, "earned": False}
        missing_fields.append("Medicare Part B coverage")

    # Wound type
    if patient_data.get("wound_type"):
        score += 20
        breakdown["wound_type"] = {"label": "Active wound type found", "points": 20, "earned": True}
    else:
        breakdown["wound_type"] = {"label": "Active wound type found", "points": 20, "earned": False}
        missing_fields.append("Wound type")

    # Stage (only relevant for pressure ulcers)
    if is_pressure_ulcer:
        if patient_data.get("wound_stage"):
            score += 10
            breakdown["stage"] = {"label": "Stage documented", "points": 10, "earned": True}
        else:
            breakdown["stage"] = {"label": "Stage documented (required for pressure ulcers)", "points": 10, "earned": False}
            missing_fields.append("Wound stage")
    else:
        breakdown["stage"] = {"label": "Stage (N/A for this wound type)", "points": 0, "earned": None}

    # Length
    if patient_data.get("length_cm") is not None:
        score += 10
        breakdown["length"] = {"label": "Length documented", "points": 10, "earned": True}
    else:
        breakdown["length"] = {"label": "Length documented", "points": 10, "earned": False}
        missing_fields.append("Wound length")

    # Width
    if patient_data.get("width_cm") is not None:
        score += 10
        breakdown["width"] = {"label": "Width documented", "points": 10, "earned": True}
    else:
        breakdown["width"] = {"label": "Width documented", "points": 10, "earned": False}
        missing_fields.append("Wound width")

    # Depth
    if patient_data.get("depth_cm") is not None:
        score += 10
        breakdown["depth"] = {"label": "Depth documented", "points": 10, "earned": True}
    else:
        breakdown["depth"] = {"label": "Depth documented", "points": 10, "earned": False}
        missing_fields.append("Wound depth")

    # Drainage
    if patient_data.get("drainage"):
        score += 10
        breakdown["drainage"] = {"label": "Drainage documented", "points": 10, "earned": True}
    else:
        breakdown["drainage"] = {"label": "Drainage documented", "points": 10, "earned": False}
        missing_fields.append("Drainage level")

    # Confidence bonus
    confidence = patient_data.get("extraction_confidence", 0) or 0
    if confidence >= 0.85:
        score += 10
        breakdown["confidence_bonus"] = {"label": "High extraction confidence", "points": 10, "earned": True}
    else:
        breakdown["confidence_bonus"] = {"label": "High extraction confidence (>85%)", "points": 10, "earned": False}

    # Ambiguity/conflict penalty
    # Check for conflicts: e.g., wound type in note doesn't match assessment
    ambiguous = _detect_ambiguity(patient_data)
    if ambiguous:
        score = max(0, score - 15)
        breakdown["ambiguity_penalty"] = {"label": "Ambiguity or data conflict detected", "points": -15, "earned": True}
    else:
        breakdown["ambiguity_penalty"] = {"label": "No ambiguity detected", "points": 0, "earned": False}

    score = max(0, min(100, score))

    # Routing decision
    if score >= 90:
        routing_decision = "auto_accept"
    elif score >= 50:
        routing_decision = "flag_for_review"
    else:
        routing_decision = "reject"

    # Generate biller action and routing reason
    biller_action, routing_reason = _generate_action(
        routing_decision, missing_fields, patient_data, score
    )

    # Generate missing documentation request
    missing_doc_request = _generate_missing_doc_request(patient_data, missing_fields) if missing_fields else None

    return {
        "claim_score": score,
        "routing_decision": routing_decision,
        "missing_fields": missing_fields,
        "score_breakdown": breakdown,
        "biller_action": biller_action,
        "routing_reason": routing_reason,
        "missing_doc_request": missing_doc_request,
    }


def _detect_ambiguity(patient_data: dict) -> bool:
    """Detect if there are conflicting signals in the data."""
    # Pressure ulcer without stage is ambiguous
    is_pressure_ulcer = patient_data.get("wound_type") in PRESSURE_ULCER_TYPES
    if is_pressure_ulcer and not patient_data.get("wound_stage"):
        return True
    # Low confidence from extraction
    conf = patient_data.get("extraction_confidence") or 0
    if conf > 0 and conf < 0.5:
        return True
    return False


def _generate_action(decision: str, missing: list, data: dict, score: int) -> tuple:
    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or data.get("patient_id", "")
    wound = data.get("wound_type") or "wound"
    location = data.get("wound_location") or ""
    stage = data.get("wound_stage") or ""

    if decision == "auto_accept":
        wound_desc = f"{stage} {wound}" if stage else wound
        wound_desc = wound_desc.strip()
        action = f"Ready to route to billing. All Medicare Part B wound documentation requirements are clearly present."
        reason = f"Active Medicare Part B coverage confirmed. {wound_desc.title()} documented with complete measurements and drainage. No documentation gaps identified."
    elif decision == "flag_for_review":
        missing_str = ", ".join(missing[:3])
        if len(missing) > 3:
            missing_str += f" and {len(missing)-3} more"
        action = f"Request updated wound documentation before submitting claim. Missing: {missing_str}."
        reason = f"Partial documentation found. {missing_str} not documented. Cannot confirm full Medicare Part B wound billing requirements are met."
    else:
        if not data.get("has_medicare_part_b"):
            action = "Patient does not have active Medicare Part B coverage. Do not route to wound care billing."
            reason = "No active Medicare Part B coverage found. Patient is not eligible for wound care billing under this payer."
        elif not data.get("wound_type"):
            action = "No billable wound documentation found in clinical records. Do not route to billing."
            reason = "No wound diagnosis or wound documentation found. Cannot establish medical necessity for wound care billing."
        else:
            action = f"Insufficient documentation ({score}/100). Do not route until complete wound records are obtained."
            reason = f"Score too low ({score}/100). Critical fields missing: {', '.join(missing[:3])}."

    return action, reason


def _generate_missing_doc_request(data: dict, missing: list) -> Optional[str]:
    if not missing:
        return None
    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or data.get("patient_id", "Patient")
    patient_id = data.get("patient_id", "")
    wound = data.get("wound_type") or "wound"
    location = data.get("wound_location") or ""
    location_str = f" at {location}" if location else ""

    present_items = []
    if data.get("wound_type"):
        present_items.append(f"wound type ({wound})")
    if data.get("length_cm") and data.get("width_cm"):
        present_items.append("length and width measurements")
    if data.get("wound_location"):
        present_items.append(f"location ({location})")

    present_str = ", ".join(present_items) if present_items else "some wound data"
    missing_str = " and ".join(missing)

    return (
        f"Re: Wound Documentation Update — {name} ({patient_id})\n\n"
        f"Please update wound documentation for patient {name}. Current records include {present_str}{location_str}, "
        f"but {missing_str} {'are' if len(missing) > 1 else 'is'} missing.\n\n"
        f"Medicare Part B wound billing review requires complete wound measurements (length, width, depth) "
        f"and drainage documentation. Please update the wound assessment at your earliest convenience so "
        f"this patient's claim can be processed."
    )
