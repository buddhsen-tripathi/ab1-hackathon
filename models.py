"""
Shared data models for the wound care billing pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RoutingDecision = Literal["auto_accept", "flag_for_review", "reject"]

# Wound-type-aware required fields for billing completeness.
# Depth determines staging for pressure ulcers — required.
# Venous ulcers are typically superficial — depth optional.
# All other types need measurements + drainage but depth is optional.
_REQUIRED_BY_WOUND_TYPE: dict[str, list[str]] = {
    "pressure ulcer": [
        "wound_type", "stage", "length_cm", "width_cm", "depth_cm", "drainage_amount"
    ],
    "diabetic foot ulcer": [
        "wound_type", "length_cm", "width_cm", "depth_cm", "drainage_amount"
    ],
    "arterial ulcer": [
        "wound_type", "length_cm", "width_cm", "depth_cm", "drainage_amount"
    ],
    "venous ulcer": [
        "wound_type", "length_cm", "width_cm", "drainage_amount"
    ],
    "venous stasis ulcer": [
        "wound_type", "length_cm", "width_cm", "drainage_amount"
    ],
}
_DEFAULT_REQUIRED = ["wound_type", "length_cm", "width_cm", "drainage_amount"]


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

    def required_fields(self) -> list[str]:
        wt = (self.wound_type or "").lower().strip()
        return _REQUIRED_BY_WOUND_TYPE.get(wt, _DEFAULT_REQUIRED)

    def missing_fields(self) -> list[str]:
        all_vals: dict[str, object] = {
            "wound_type":     self.wound_type,
            "stage":          self.stage,
            "length_cm":      self.length_cm,
            "width_cm":       self.width_cm,
            "depth_cm":       self.depth_cm,
            "drainage_amount": self.drainage_amount,
        }
        return [f for f in self.required_fields() if all_vals.get(f) is None]

    def is_complete(self) -> bool:
        return not self.missing_fields()
