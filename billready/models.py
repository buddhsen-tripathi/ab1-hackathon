from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RoutingDecision = Literal["auto_accept", "flag_for_review", "reject"]
DrainageAmount = Literal["none", "light", "moderate", "heavy"]


@dataclass
class WoundExtraction:
    wound_type: str | None = None
    stage: str | None = None
    location: str | None = None
    length_cm: float | None = None
    width_cm: float | None = None
    depth_cm: float | None = None
    drainage_amount: str | None = None
    source: str = "unknown"
    confidence: float = 0.0
    raw_snippet: str | None = None
    evidence: dict[str, str] = field(default_factory=dict)

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.wound_type:
            missing.append("wound_type")
        if self.length_cm is None:
            missing.append("length_cm")
        if self.width_cm is None:
            missing.append("width_cm")
        if self.depth_cm is None:
            missing.append("depth_cm")
        if not self.drainage_amount:
            missing.append("drainage_amount")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0


@dataclass
class PatientRecord:
    internal_id: int
    patient_id: str
    facility_id: int
    first_name: str | None
    last_name: str | None
    primary_payer_code: str | None
    is_new_admission: bool
    diagnoses: list[dict] = field(default_factory=list)
    coverage: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)
    assessments: list[dict] = field(default_factory=list)


@dataclass
class EligibilityResult:
    internal_id: int
    patient_id: str
    facility_id: int
    first_name: str | None
    last_name: str | None
    is_new_admission: bool
    has_active_mcb: bool
    wound_type: str | None
    stage: str | None
    location: str | None
    length_cm: float | None
    width_cm: float | None
    depth_cm: float | None
    drainage_amount: str | None
    extraction_source: str
    extraction_confidence: float
    routing_decision: RoutingDecision
    reason: str
    submission_eligible: bool = False
    missing_fields: list[str] = field(default_factory=list)
    llm_check: str | None = None
    llm_check_note: str | None = None
