from __future__ import annotations

import streamlit as st

COLORS = {
    "bg": "#f4f6f8",
    "surface": "#ffffff",
    "border": "#e2e8f0",
    "text": "#1a2332",
    "muted": "#64748b",
    "accent": "#2563eb",
    "auto_accept": "#059669",
    "auto_accept_bg": "#ecfdf5",
    "flag_for_review": "#b45309",
    "flag_for_review_bg": "#fffbeb",
    "reject": "#b91c1c",
    "reject_bg": "#fef2f2",
}

ROUTING_CONFIG = {
    "auto_accept": {
        "label": "Ready to Bill",
        "color": COLORS["auto_accept"],
        "bg": COLORS["auto_accept_bg"],
    },
    "flag_for_review": {
        "label": "Needs Review",
        "color": COLORS["flag_for_review"],
        "bg": COLORS["flag_for_review_bg"],
    },
    "reject": {
        "label": "Do Not Route",
        "color": COLORS["reject"],
        "bg": COLORS["reject_bg"],
    },
}

FACILITY_NAMES = {101: "Facility A", 102: "Facility B", 103: "Facility C"}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

        .stApp {{
            background-color: {COLORS["bg"]};
        }}

        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        html, body, [class*="css"] {{
            font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        }}

        section[data-testid="stSidebar"] {{
            background-color: {COLORS["surface"]};
            border-right: 1px solid {COLORS["border"]};
        }}

        h1 {{
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
            padding-bottom: 0 !important;
        }}

        div[data-testid="stMetric"] {{
            background: {COLORS["surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 10px;
            padding: 12px 16px;
        }}

        div[data-testid="stMetric"] label {{
            font-size: 0.72rem !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: {COLORS["muted"]} !important;
        }}

        div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
            font-size: 1.6rem !important;
            font-weight: 700 !important;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 8px !important;
            border-color: {COLORS["border"]} !important;
            margin-bottom: 8px;
        }}

        div[data-testid="column"] .stButton > button {{
            font-size: 0.76rem;
            font-weight: 600;
            border-radius: 6px;
            border: 1px solid {COLORS["border"]};
            color: {COLORS["muted"]};
            background: {COLORS["surface"]};
        }}

        div[data-testid="column"] .stButton > button:hover {{
            border-color: {COLORS["accent"]};
            color: {COLORS["accent"]};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
