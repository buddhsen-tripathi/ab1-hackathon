"""Canonical extraction schema + controlled vocabularies.

Every parser, regardless of source format, emits a WoundExtraction. That
uniformity is what lets the routing engine reason over one shape.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional

# --- controlled vocabularies ---------------------------------------------

WOUND_TYPES = {
    "pressure_ulcer",
    "diabetic_foot_ulcer",
    "venous_ulcer",
    "arterial_ulcer",
    "surgical_site_infection",
    "abscess",
    "burn",
    "other",
}

DRAINAGE_LEVELS = {"none", "light", "moderate", "heavy"}
LATERALITIES = {"left", "right", "bilateral"}

# Flags the routing engine reads. Presence of any "blocking" flag means the
# record is not safely auto-acceptable on its own.
BLOCKING_FLAGS = {
    "missing_depth",
    "missing_measurements",
    "missing_drainage",
    "missing_wound_type",
    "laterality_conflict",
    "multi_wound",
    "implausible_measurement",
    "unparseable",
}


@dataclass
class WoundExtraction:
    patient_id: int
    source_doc: str            # 'note' | 'assessment'
    source_doc_id: int
    source_format: str         # assessment_structured | assessment_narrative
                               #  | note_soap | note_envive | note_shorthand | unknown
    method: str                # structured_field | regex | llm
    wound_index: int = 0       # 0-based; >0 only for multi-wound documents
    is_primary: bool = True

    wound_type: Optional[str] = None
    stage: Optional[str] = None            # '2','3','4','unstageable','dti' or None
    location: Optional[str] = None
    laterality: Optional[str] = None
    length_cm: Optional[float] = None
    width_cm: Optional[float] = None
    depth_cm: Optional[float] = None
    area_cm2: Optional[float] = None
    drainage_amount: Optional[str] = None
    drainage_type: Optional[str] = None

    has_all_measurements: bool = False     # L & W & D all present
    billing_ready: bool = False            # complete + no blocking flags
    confidence: float = 0.0
    flags: list = field(default_factory=list)
    raw_span: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def finalize(self):
        """Compute derived fields + billing readiness from what was parsed."""
        if self.length_cm is not None and self.width_cm is not None:
            self.area_cm2 = round(self.length_cm * self.width_cm, 2)

        self.has_all_measurements = (
            self.length_cm is not None
            and self.width_cm is not None
            and self.depth_cm is not None
        )

        # auto-derive completeness flags
        if self.wound_type is None:
            self._flag("missing_wound_type")
        if not self.has_all_measurements:
            if self.length_cm is None and self.width_cm is None:
                self._flag("missing_measurements")
            elif self.depth_cm is None:
                self._flag("missing_depth")
        if self.drainage_amount is None:
            self._flag("missing_drainage")

        blocking = any(f in BLOCKING_FLAGS for f in self.flags)
        self.billing_ready = (
            self.wound_type is not None
            and self.has_all_measurements
            and self.drainage_amount is not None
            and not blocking
            and self.confidence >= 0.6
        )
        return self

    def _flag(self, name):
        if name not in self.flags:
            self.flags.append(name)

    def as_row(self):
        return asdict(self)
