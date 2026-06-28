"""ICD-10 wound-diagnosis gate.

A Medicare Part B claim is denied without a supporting diagnosis code, so a
documented wound is only billable if the patient also has an *active* wound
ICD-10 on record. These prefixes cover the billable wound conditions.
"""

WOUND_ICD_PREFIXES = (
    "L89",     # pressure ulcer
    "E11.62",  # type 2 diabetic foot ulcer
    "E10.62",  # type 1 diabetic foot ulcer
    "I83",     # venous ulcer
    "I70.2",   # arterial ulcer
    "L02",     # abscess / cellulitis
    "L97",     # non-pressure ulcer of lower limb
    "L98",     # other chronic skin ulcer
    "T20", "T21", "T22", "T23", "T24", "T25",  # burns
)


def is_wound_code(code) -> bool:
    code = (code or "").strip().upper()
    return any(code.startswith(p) for p in WOUND_ICD_PREFIXES)
