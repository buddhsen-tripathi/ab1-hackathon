"""Eligibility / routing layer (Task 3).

Consumes the per-document `wound_extractions` rows, reconciles each patient's
sources into one wound (merge-to-fill-gaps + cross-source conflict flagging),
applies the coverage filter + routing cascade, and writes one
`patient_eligibility` row per patient: the biller-facing output table.

Logic adapted from the liliia/BillReady blueprint (coverage filter, required
fields, 0.75/0.4 thresholds, source fusion) with our addition: conflicts
between sources are flagged for review instead of silently merged.
"""
