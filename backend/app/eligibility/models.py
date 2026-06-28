"""Output schema: one EligibilityResult per patient (the biller's table)."""
from dataclasses import dataclass, field, asdict
from typing import Optional

# Wound-type-aware required fields (clinical refinement). Depth is staging-
# critical for deep wounds (pressure / diabetic / arterial) but a venous ulcer
# is superficial, so depth is optional there; pressure ulcers additionally need
# a stage. Keys are our canonical enum values. This is a deliberate deviation
# from the README's blanket "L/W/D" — documented because it's clinically sound
# and stops superficial wounds being flagged for a depth they don't need.
REQUIRED_BY_TYPE = {
    "pressure_ulcer": ["wound_type", "stage", "length_cm", "width_cm", "depth_cm", "drainage_amount"],
    "diabetic_foot_ulcer": ["wound_type", "length_cm", "width_cm", "depth_cm", "drainage_amount"],
    "arterial_ulcer": ["wound_type", "length_cm", "width_cm", "depth_cm", "drainage_amount"],
    "venous_ulcer": ["wound_type", "length_cm", "width_cm", "drainage_amount"],
}
DEFAULT_REQUIRED = ["wound_type", "length_cm", "width_cm", "drainage_amount"]


def required_fields(wound_type):
    return REQUIRED_BY_TYPE.get((wound_type or "").lower().strip(), DEFAULT_REQUIRED)


FIELD_LABELS = {
    "wound_type": "wound type",
    "stage": "stage",
    "length_cm": "length",
    "width_cm": "width",
    "depth_cm": "depth",
    "drainage_amount": "drainage",
    "medicare_part_b": "Medicare Part B coverage",
    "wound_documentation": "wound documentation",
    "wound_diagnosis": "active wound ICD-10 diagnosis",
    "wound_type_conflict": "wound-type disagreement between sources",
    "laterality_conflict": "left/right disagreement",
    "drainage_conflict": "drainage disagreement between sources",
    "measurement_conflict": "measurement disagreement between sources",
    "multi_wound": "multiple wounds — primary ambiguous",
    "implausible_measurement": "implausible measurement",
}


@dataclass
class EligibilityResult:
    internal_id: int
    patient_id: str
    facility_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    is_new_admission: bool
    has_active_mcb: bool
    submission_eligible: bool
    wound_type: Optional[str]
    stage: Optional[str]
    location: Optional[str]
    laterality: Optional[str]
    length_cm: Optional[float]
    width_cm: Optional[float]
    depth_cm: Optional[float]
    area_cm2: Optional[float]
    drainage_amount: Optional[str]
    extraction_source: str
    extraction_confidence: float
    routing_decision: str            # auto_accept | flag_for_review | reject
    reason: str
    missing_fields: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    secondary_wound_count: int = 0

    def as_row(self):
        return asdict(self)
