"""Preprocessing layer.

Turns raw notes + assessments into clean, normalized, flagged wound records
(`wound_extractions` table) that the downstream routing engine consumes to
decide auto_accept / reject / flag_for_review.

Deterministic only (structured-field reader + regex parsers). The abbreviation
knowledge base and LLM fallback plug in later at the `normalize.expand_abbreviations`
and `parsers.parse_document` seams.
"""
