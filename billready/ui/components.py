from __future__ import annotations

import html
import json

import streamlit as st

from billready.extraction.evidence import build_evidence_html
from billready.extraction.fusion import extract_patient_wound
from billready.models import PatientRecord
from billready.storage.cache import CacheStore
from billready.ui.styles import FACILITY_NAMES, ROUTING_CONFIG


def render_header(subtitle: str = "Medicare Part B wound care billing worklist") -> None:
    st.title("BillReady")
    st.caption(subtitle)


def render_metrics(
    filtered: list[dict],
    results: list[dict],
    counts: dict[str, int],
    mcb: int,
    filters_active: bool,
) -> None:
    if filters_active:
        st.caption(f"Showing {len(filtered)} of {len(results)} patients")

    cols = st.columns(6)
    submission_eligible = sum(
        1 for r in filtered if r.get("submission_eligible") in (True, "True")
        or r.get("has_active_mcb") in (True, "True")
    )
    labels = [
        ("Shown", len(filtered)),
        ("Part B eligible", submission_eligible),
        ("Ready to bill", counts["auto_accept"]),
        ("Needs review", counts["flag_for_review"]),
        ("Not eligible", counts["reject"]),
        ("LLM suggestions", sum(
            1 for r in filtered
            if r.get("llm_check") in ("billable", "needs_documentation", "unclear")
        )),
    ]
    for col, (label, value) in zip(cols, labels):
        col.metric(label, value)


def _is_submission_eligible(row: dict) -> bool:
    return row.get("submission_eligible") in (True, "True") or row.get("has_active_mcb") in (
        True,
        "True",
    )


def _payer_badge(row: dict) -> str:
    if _is_submission_eligible(row):
        return (
            "<span style='background:#dcfce7;color:#166534;font-size:0.65rem;font-weight:700;"
            "padding:2px 7px;border-radius:4px;margin-right:4px;'>PART B ELIGIBLE</span>"
        )
    return (
        "<span style='background:#fee2e2;color:#991b1b;font-size:0.65rem;font-weight:700;"
        "padding:2px 7px;border-radius:4px;margin-right:4px;'>NOT PART B</span>"
    )


def _wound_summary(row: dict) -> str:
    parts = []
    if row.get("wound_type"):
        stage = f", stage {row['stage']}" if row.get("stage") else ""
        parts.append(f"{row['wound_type']}{stage}")
    if row.get("location"):
        parts.append(row["location"])
    dims = [str(row[k]) for k in ("length_cm", "width_cm", "depth_cm") if row.get(k)]
    if dims:
        parts.append(" × ".join(dims) + " cm")
    if row.get("drainage_amount"):
        parts.append(f"{row['drainage_amount']} drainage")
    return " · ".join(parts) if parts else "No wound data extracted"


def _render_inline_detail(row: dict, cache: CacheStore) -> None:
    st.caption(row.get("reason", ""))

    if row.get("llm_check") and row.get("llm_check") != "skipped":
        st.caption(f"AI suggestion: {row.get('llm_check_note', '')}")

    dims = " × ".join(str(row[k]) for k in ("length_cm", "width_cm", "depth_cm") if row.get(k))
    if dims:
        dims += " cm"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.write(f"**Type:** {row.get('wound_type') or '—'}")
    c2.write(f"**Stage:** {row.get('stage') or '—'}")
    c3.write(f"**Location:** {row.get('location') or '—'}")
    c4.write(f"**Size:** {dims or '—'}")
    c5.write(f"**Drainage:** {row.get('drainage_amount') or '—'}")

    patient_id = row["patient_id"]
    internal_id = int(row["internal_id"])
    notes = cache.get_patient_notes(internal_id)
    assessments = cache.get_patient_assessments(internal_id)
    coverage = cache.get_patient_coverage(patient_id)
    diagnoses = cache.get_patient_diagnoses(patient_id)

    record = PatientRecord(
        internal_id=internal_id,
        patient_id=patient_id,
        facility_id=int(row["facility_id"]),
        first_name=row.get("first_name"),
        last_name=row.get("last_name"),
        primary_payer_code=None,
        is_new_admission=row.get("is_new_admission") in (True, "True"),
        diagnoses=diagnoses,
        coverage=coverage,
        notes=notes,
        assessments=assessments,
    )
    wound = extract_patient_wound(record)

    ntab, atab, ctab = st.tabs(["Note", "Assessment", "Coverage"])
    with ntab:
        if notes:
            note_text = notes[0].get("note_text") or ""
            st.markdown(build_evidence_html(note_text, wound), unsafe_allow_html=True)
        else:
            st.write("No note on file.")
    with atab:
        if assessments:
            for ass in assessments:
                st.caption(f"{ass.get('assessment_type')} · {ass.get('assessment_date')}")
                raw = ass.get("raw_json")
                try:
                    st.json(json.loads(raw) if isinstance(raw, str) else raw)
                except (json.JSONDecodeError, TypeError):
                    st.text(raw or "")
        else:
            st.write("No assessment on file.")
    with ctab:
        if coverage:
            for c in coverage:
                active = "Active" if not c.get("effective_to") else "Ended"
                st.write(f"**{c.get('payer_name')}** ({c.get('payer_code')}) — {active}")
        else:
            st.write("No coverage.")
        if diagnoses:
            st.markdown("**Diagnoses**")
            for d in diagnoses:
                if d.get("clinical_status") == "active":
                    st.write(f"`{d.get('icd10_code')}` {d.get('icd10_description')}")


def _render_patient_card(row: dict, cache: CacheStore, key_prefix: str, index: int) -> None:
    name = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip() or "Unknown"
    facility = FACILITY_NAMES.get(int(row["facility_id"]), str(row["facility_id"]))
    summary = _wound_summary(row)
    is_new = row.get("is_new_admission") in (True, "True")
    new_tag = " · NEW" if is_new else ""

    label = f"{row['patient_id']} — {name}{new_tag}"
    with st.expander(label, expanded=False):
        st.markdown(_payer_badge(row), unsafe_allow_html=True)
        st.caption(f"{facility} · {float(row.get('extraction_confidence') or 0):.0%} confidence")
        st.write(summary[:160] + ("…" if len(summary) > 160 else ""))
        _render_inline_detail(row, cache)


def render_kanban_column(
    decision: str,
    patients: list[dict],
    cache: CacheStore,
    key_prefix: str,
) -> None:
    cfg = ROUTING_CONFIG[decision]

    st.markdown(
        f"<div style='background:{cfg['bg']};border-left:4px solid {cfg['color']};"
        f"padding:10px 14px;border-radius:6px;margin-bottom:12px;'>"
        f"<span style='font-weight:700;font-size:0.8rem;color:{cfg['color']};"
        f"text-transform:uppercase;letter-spacing:0.04em;'>{cfg['label']}</span>"
        f"<span style='float:right;background:white;padding:2px 10px;border-radius:99px;"
        f"font-size:0.75rem;color:#64748b;font-weight:600;'>{len(patients)}</span></div>",
        unsafe_allow_html=True,
    )

    if not patients:
        st.caption("No patients in this queue")
        return

    for i, row in enumerate(patients[:50]):
        _render_patient_card(row, cache, key_prefix, i)

    if len(patients) > 50:
        st.caption(f"+ {len(patients) - 50} more not shown")


def render_sidebar_stats(results: list[dict], stats: dict, run_stats: dict) -> None:
    st.markdown("##### Pipeline")
    if run_stats:
        c1, c2 = st.columns(2)
        c1.metric("Runtime", f"{run_stats.get('elapsed_seconds', '?')}s")
        c2.metric("API calls", run_stats.get("api_requests", "—"))
        st.caption(
            f"Rate limits: {run_stats.get('rate_limited', '—')} · "
            f"Cached: {stats.get('cached_endpoints', 0)} endpoints"
        )
    if stats.get("last_full_sync"):
        st.caption(f"Last sync: {stats['last_full_sync'][:19].replace('T', ' ')}")

    st.markdown("##### By facility")
    for fid, fname in FACILITY_NAMES.items():
        fac = [r for r in results if int(r["facility_id"]) == fid]
        ready = sum(1 for r in fac if r["routing_decision"] == "auto_accept")
        st.progress(ready / len(fac) if fac else 0, text=f"{fname}: {ready} ready / {len(fac)}")
