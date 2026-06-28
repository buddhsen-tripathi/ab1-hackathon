from __future__ import annotations

import streamlit as st

from billready.storage.cache import CacheStore
from billready.ui.components import (
    render_header,
    render_kanban_column,
    render_metrics,
    render_sidebar_stats,
)
from billready.ui.styles import FACILITY_NAMES, ROUTING_CONFIG, inject_css


def _is_submission_eligible(row: dict) -> bool:
    return row.get("submission_eligible") in (True, "True") or row.get("has_active_mcb") in (
        True,
        "True",
    )


def main() -> None:
    st.set_page_config(
        page_title="BillReady",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    cache = CacheStore()
    results = cache.load_eligibility_results()

    if not results:
        render_header("No data loaded yet")
        st.warning("Run the pipeline first to load patient data.")
        st.code("python run_pipeline.py", language="bash")
        return

    stats = cache.get_cache_stats()
    run_stats = stats.get("last_pipeline_run") or {}

    with st.sidebar:
        st.markdown("##### Filters")
        facility_filter = st.selectbox(
            "Facility",
            ["All", "101", "102", "103"],
            format_func=lambda x: "All facilities" if x == "All" else FACILITY_NAMES.get(int(x), x),
        )
        routing_filter = st.multiselect(
            "Documentation status",
            list(ROUTING_CONFIG.keys()),
            default=list(ROUTING_CONFIG.keys()),
            format_func=lambda x: ROUTING_CONFIG[x]["label"],
        )
        payer_filter = st.selectbox(
            "Part B submission eligibility",
            ["All", "eligible", "not_eligible"],
            format_func=lambda x: {
                "All": "All patients",
                "eligible": "Part B eligible only",
                "not_eligible": "Not Part B eligible",
            }[x],
        )
        new_only = st.toggle("New admissions only", value=False)
        search = st.text_input("Search", placeholder="Patient ID or name…")

        st.divider()
        render_sidebar_stats(results, stats, run_stats)

        if st.button("Refresh", use_container_width=True):
            st.rerun()

    render_header()

    filtered = results
    if facility_filter != "All":
        filtered = [r for r in filtered if str(r["facility_id"]) == facility_filter]
    if routing_filter:
        filtered = [r for r in filtered if r["routing_decision"] in routing_filter]
    if payer_filter == "eligible":
        filtered = [r for r in filtered if _is_submission_eligible(r)]
    elif payer_filter == "not_eligible":
        filtered = [r for r in filtered if not _is_submission_eligible(r)]
    if new_only:
        filtered = [r for r in filtered if r.get("is_new_admission") in (True, "True")]
    if search:
        q = search.lower()
        filtered = [
            r
            for r in filtered
            if q in r["patient_id"].lower()
            or q in (r.get("first_name") or "").lower()
            or q in (r.get("last_name") or "").lower()
        ]

    counts = {k: 0 for k in ROUTING_CONFIG}
    mcb = 0
    for r in filtered:
        counts[r["routing_decision"]] += 1
        if _is_submission_eligible(r):
            mcb += 1

    render_metrics(filtered, results, counts, mcb, len(filtered) != len(results))

    col1, col2, col3 = st.columns(3, gap="medium")
    groups = {
        decision: [r for r in filtered if r["routing_decision"] == decision]
        for decision in ["auto_accept", "flag_for_review", "reject"]
    }

    with col1:
        render_kanban_column("auto_accept", groups["auto_accept"], cache, "accept")
    with col2:
        render_kanban_column("flag_for_review", groups["flag_for_review"], cache, "review")
    with col3:
        render_kanban_column("reject", groups["reject"], cache, "reject")


if __name__ == "__main__":
    main()
