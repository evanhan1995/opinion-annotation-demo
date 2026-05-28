# -*- coding: utf-8 -*-
"""Centralized theme: brand palette, semantic colors, CSS injection, layout helpers.

Import this module and call inject_css() once after st.set_page_config().
All other modules import SEMANTIC_COLORS to replace hardcoded hex values.
"""

import streamlit as st

# ═══════════════════════════════════════════════════════════════════════════════
# Brand palette
# ═══════════════════════════════════════════════════════════════════════════════

BRAND_COLORS = {
    "primary": "#1a237e",
    "secondary": "#0d47a1",
    "accent": "#00bcd4",
    "bg": "#f8f9fa",
    "card": "#ffffff",
    "text": "#263238",
    "muted": "#78909c",
    "border": "#e0e0e0",
}

# ═══════════════════════════════════════════════════════════════════════════════
# Semantic color maps (extracted from shared.py + tab_knowledge.py)
# ═══════════════════════════════════════════════════════════════════════════════

SEMANTIC_COLORS = {
    "severity": {
        "P0": "#dc3545",
        "P1": "#fd7e14",
        "P2": "#ffc107",
        "P3": "#28a745",
    },
    "action": {
        "立即处理": "#dc3545",
        "持续观察": "#ffc107",
        "可忽略": "#6c757d",
        "正面可利用": "#28a745",
    },
    "category": {
        "商品问题": "#fd7e14",
        "商品侵权问题": "#dc3545",
        "售后问题": "#6f42c1",
        "数据泄露": "#e83e8c",
        "软件问题": "#0d6efd",
        "其他": "#6c757d",
    },
    "traffic_light": {
        "红": "#dc3545",
        "黄": "#ffc107",
        "绿": "#28a745",
    },
    "kb_status": {
        "待跟进": "#0d6efd",
        "处理中": "#fd7e14",
        "已处理": "#198754",
        "已放弃": "#6c757d",
        "忽略": "#6c757d",
    },
    "alert": {
        "P0": "#dc3545",
        "P1": "#ff9800",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# CSS injection
# ═══════════════════════════════════════════════════════════════════════════════

def inject_css():
    """Inject custom CSS via st.markdown. Call once after st.set_page_config()."""
    css = f"""
    <style>
    /* ── Typography ───────────────────────────────────────────────── */
    html, body, [class*="css"] {{
        font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC",
                     -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}

    h1 {{
        color: {BRAND_COLORS['primary']};
        font-weight: 700;
        border-bottom: 2px solid #e8eaf6;
        padding-bottom: 0.5rem;
    }}

    h2, h3 {{
        color: {BRAND_COLORS['text']};
    }}

    /* ── Sidebar ──────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {{
        width: 280px !important;
        background-color: #fafbfc;
        border-right: 1px solid {BRAND_COLORS['border']};
    }}

    section[data-testid="stSidebar"] .st-emotion-cache-1wmy9hl {{
        gap: 0.25rem;
    }}

    /* Sidebar expander headers */
    section[data-testid="stSidebar"] .streamlit-expanderHeader {{
        font-size: 0.9rem;
        padding: 0.4rem 0.5rem;
    }}

    /* Sidebar metric containers */
    section[data-testid="stSidebar"] [data-testid="metric-container"] {{
        padding: 0.25rem 0.5rem;
        font-size: 0.85rem;
    }}

    /* ── Main content ─────────────────────────────────────────────── */
    .main > div {{
        padding: 1rem 2rem;
    }}

    /* ── Buttons ──────────────────────────────────────────────────── */
    div.stButton > button {{
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.15s ease;
    }}

    div.stButton > button[kind="primary"] {{
        background-color: {BRAND_COLORS['primary']};
        color: white;
        border: none;
    }}

    div.stButton > button[kind="primary"]:hover {{
        background-color: {BRAND_COLORS['secondary']};
        box-shadow: 0 2px 6px rgba(26,35,126,0.3);
    }}

    div.stButton > button[kind="secondary"] {{
        background-color: transparent;
        color: #455a64;
        border: 1px solid #cfd8dc;
    }}

    div.stButton > button[kind="secondary"]:hover {{
        background-color: #eceff1;
        border-color: #b0bec5;
    }}

    /* ── Metric cards ─────────────────────────────────────────────── */
    div[data-testid="metric-container"] {{
        background: {BRAND_COLORS['card']};
        border: 1px solid #eceff1;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}

    /* ── Expanders ────────────────────────────────────────────────── */
    .streamlit-expanderHeader {{
        font-weight: 500;
        border-radius: 6px;
        font-size: 0.95rem;
    }}

    /* ── Alerts ───────────────────────────────────────────────────── */
    div.stAlert {{
        border-radius: 8px;
        border-left-width: 4px;
    }}

    /* ── Dividers ─────────────────────────────────────────────────── */
    hr {{
        margin: 6px 0;
        border: 0;
        border-top: 1px solid {BRAND_COLORS['border']};
    }}

    /* ── Tab navigation bar (Phase 1) ─────────────────────────────── */
    .tab-nav-row {{
        display: flex;
        gap: 4px;
        padding: 6px 0;
        border-bottom: 2px solid #e8eaf6;
        margin-bottom: 1rem;
    }}

    /* ── Login card ───────────────────────────────────────────────── */
    .login-card {{
        background: {BRAND_COLORS['card']};
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        margin-top: 1rem;
    }}

    /* ── Misc ─────────────────────────────────────────────────────── */
    div[data-testid="stCaptionContainer"] {{
        color: {BRAND_COLORS['muted']};
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Layout helpers
# ═══════════════════════════════════════════════════════════════════════════════

def spacer(height: str = "0.5rem"):
    """Vertical spacer to replace st.caption('') hacks."""
    st.markdown(
        f'<div style="height:{height}"></div>',
        unsafe_allow_html=True,
    )


def badge_html(text: str, color: str) -> str:
    """Return HTML for a colored inline badge span."""
    return (
        f"<span style='background:{color};color:white;padding:2px 10px;"
        f"border-radius:10px;font-size:0.85em;'>{text}</span>"
    )


def section_header(label: str):
    """Render a consistent section heading."""
    st.markdown(
        f"<p style='color:{BRAND_COLORS['primary']};font-weight:600;"
        f"font-size:0.95rem;margin:0.5rem 0 0.25rem 0;'>{label}</p>",
        unsafe_allow_html=True,
    )
