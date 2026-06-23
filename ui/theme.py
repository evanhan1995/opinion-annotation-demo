# -*- coding: utf-8 -*-
"""Centralized theme: brand palette, semantic colors, CSS injection, layout helpers.

Import this module and call inject_css() once after st.set_page_config().
All other modules import SEMANTIC_COLORS to replace hardcoded hex values.
"""

import streamlit as st

# ═══════════════════════════════════════════════════════════════════════════════
# Brand palette — 现代蓝调 (企业简洁版)
# ═══════════════════════════════════════════════════════════════════════════════

BRAND_COLORS = {
    "primary": "#0D47A1",
    "secondary": "#1565C0",
    "accent": "#00ACC1",
    "bg": "#f0f2f5",
    "card": "#ffffff",
    "text": "#1a1a2e",
    "muted": "#64748B",
    "border": "#e2e8f0",
}

# ═══════════════════════════════════════════════════════════════════════════════
# Typography scale — 企业字体层级
# ═══════════════════════════════════════════════════════════════════════════════

TYPOGRAPHY = {
    "base_size": "15px",
    "h1": {"size": "1.6rem", "weight": "700"},
    "h2": {"size": "1.25rem", "weight": "600"},
    "h3": {"size": "1.05rem", "weight": "600"},
    "body": {"size": "0.95rem", "weight": "400"},
    "caption": {"size": "0.8rem", "weight": "400"},
    "label": {"size": "0.85rem", "weight": "500"},
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
    P = BRAND_COLORS
    css = f"""
    <style>
    /* ═══════════════════════════════════════════════════════════════════
       Base & Typography — 企业简洁字体层级
       ═══════════════════════════════════════════════════════════════════ */
    html {{
        font-size: {TYPOGRAPHY['base_size']};
    }}

    html, body, [class*="css"] {{
        font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC",
                     -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}

    h1 {{
        color: {P['text']};
        font-size: {TYPOGRAPHY['h1']['size']};
        font-weight: {TYPOGRAPHY['h1']['weight']};
        border-bottom: 1px solid {P['border']};
        padding-bottom: 0.5rem;
        letter-spacing: -0.01em;
        margin-top: 0.25rem;
        margin-bottom: 0.75rem;
    }}

    h2 {{
        color: {P['text']};
        font-size: {TYPOGRAPHY['h2']['size']};
        font-weight: {TYPOGRAPHY['h2']['weight']};
        letter-spacing: -0.005em;
        margin-top: 0.5rem;
        margin-bottom: 0.4rem;
    }}

    h3 {{
        color: {P['text']};
        font-size: {TYPOGRAPHY['h3']['size']};
        font-weight: {TYPOGRAPHY['h3']['weight']};
        margin-top: 0.3rem;
        margin-bottom: 0.3rem;
    }}

    p, li, .stMarkdown {{
        font-size: {TYPOGRAPHY['body']['size']};
        line-height: 1.6;
        color: {P['text']};
    }}

    label {{
        font-size: {TYPOGRAPHY['label']['size']} !important;
        font-weight: {TYPOGRAPHY['label']['weight']} !important;
        color: {P['text']} !important;
    }}

    div[data-testid="stCaptionContainer"] {{
        color: {P['muted']} !important;
        font-size: {TYPOGRAPHY['caption']['size']} !important;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Sidebar — 企业简洁侧边栏
       ═══════════════════════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {{
        width: 280px !important;
        background-color: #f8fafc;
        border-right: 1px solid {P['border']};
    }}

    section[data-testid="stSidebar"] .st-emotion-cache-1wmy9hl {{
        gap: 0.15rem;
    }}

    /* Sidebar expander headers with left blue decoration */
    section[data-testid="stSidebar"] .streamlit-expanderHeader {{
        font-size: 0.9rem;
        font-weight: 600;
        padding: 0.4rem 0.5rem;
        border-left: 3px solid {P['primary']};
        padding-left: 0.6rem;
        border-radius: 0;
        margin-bottom: 2px;
        transition: background 0.15s ease;
    }}

    section[data-testid="stSidebar"] .streamlit-expanderHeader:hover {{
        background: #f1f5f9;
    }}

    /* Sidebar inner expander content spacing */
    section[data-testid="stSidebar"] .streamlit-expanderContent {{
        padding: 0.25rem 0.5rem 0.5rem 0.75rem;
    }}

    /* Sidebar metric containers */
    section[data-testid="stSidebar"] [data-testid="metric-container"] {{
        padding: 0.2rem 0.4rem;
        background: transparent;
        border: none;
        box-shadow: none;
    }}

    /* Sidebar divider refinements */
    section[data-testid="stSidebar"] hr {{
        margin: 8px 0;
        border-top: 1px solid {P['border']};
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Main content — 企业简洁主内容区（居中约束）
       ═══════════════════════════════════════════════════════════════════ */
    .main > div {{
        padding: 1.2rem 2rem;
        max-width: 1400px;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Buttons — 企业简洁按钮
       ═══════════════════════════════════════════════════════════════════ */
    div.stButton > button {{
        border-radius: 8px;
        font-weight: 500;
        font-size: 0.9rem;
        padding: 0.35rem 1rem;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid transparent;
    }}

    div.stButton > button[kind="primary"] {{
        background: {P['primary']};
        color: white;
        border: none;
    }}

    div.stButton > button[kind="primary"]:hover {{
        background: {P['secondary']};
        box-shadow: 0 3px 8px rgba(13,71,161,0.25);
        transform: translateY(-1px);
    }}

    div.stButton > button[kind="primary"]:active {{
        transform: translateY(0);
        box-shadow: 0 1px 3px rgba(13,71,161,0.2);
    }}

    div.stButton > button[kind="secondary"] {{
        background-color: transparent;
        color: {P['muted']};
        border: 1px solid {P['border']};
    }}

    div.stButton > button[kind="secondary"]:hover {{
        background-color: #f8fafc;
        border-color: #cbd5e1;
        color: {P['text']};
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Tab navigation — 企业简洁标签导航 (active 下划线)
       ═══════════════════════════════════════════════════════════════════ */
    .tab-nav-row {{
        display: flex;
        gap: 4px;
        padding: 6px 0;
        border-bottom: 2px solid {P['border']};
        margin-bottom: 0.2rem;
    }}

        /* Topbar - brand header (matching HTML design) */
     .topbar {{
        background: linear-gradient(135deg, #0D47A1, #1565C0);
        border-radius: 10px 10px 0 0;
        padding: 0.5rem 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 8px rgba(13,71,161,0.15);
    }}
    .topbar-left {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .topbar-logo {{
        font-size: 1.4rem;
        line-height: 1;
    }}
    .topbar-title {{
        color: #ffffff;
        font-size: 17px;
        font-weight: 700;
        white-space: nowrap;
    }}
    .topbar-right {{
        display: flex;
        align-items: center;
        gap: 10px;
        color: #fff;
        font-size: 13px;
    }}
    .topbar-avatar {{
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #00ACC1;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 600;
        color: #fff;
    }}

    /*         /* ═══════════════════════════════════════════════════════════════════
       Expanders — 企业简洁折叠面板
       ═══════════════════════════════════════════════════════════════════ */
    .streamlit-expanderHeader {{
        font-size: {TYPOGRAPHY['body']['size']};
        font-weight: 500;
        border-radius: 8px;
        background: #fafbfc;
        padding: 0.4rem 0.75rem;
        transition: background 0.15s ease;
    }}

    .streamlit-expanderHeader:hover {{
        background: #f1f5f9;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Alerts — 企业简洁告警
       ═══════════════════════════════════════════════════════════════════ */
    div.stAlert {{
        border-radius: 10px;
        border-left-width: 4px;
        font-size: 0.9rem;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Dividers — 企业简洁分割线
       ═══════════════════════════════════════════════════════════════════ */
    hr {{
        margin: 6px 0;
        border: 0;
        border-top: 1px solid {P['border']};
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Login card — 企业简洁登录卡片 (顶部蓝条)
       ═══════════════════════════════════════════════════════════════════ */
    .login-card {{
        background: {P['card']};
        padding: 2.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        border: 1px solid {P['border']};
        border-top: 3px solid {P['primary']};
        margin-top: 1rem;
    }}

    .login-card input:focus {{
        border-color: {P['primary']} !important;
        box-shadow: 0 0 0 2px rgba(13,71,161,0.12) !important;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Scrollbar — 企业简洁滚动条
       ═══════════════════════════════════════════════════════════════════ */
    ::-webkit-scrollbar {{
        width: 6px;
        height: 6px;
    }}

    ::-webkit-scrollbar-track {{
        background: transparent;
    }}

    ::-webkit-scrollbar-thumb {{
        background: #cbd5e1;
        border-radius: 3px;
    }}

    ::-webkit-scrollbar-thumb:hover {{
        background: #94a3b8;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Status dot — 值守状态脉冲动画
       ═══════════════════════════════════════════════════════════════════ */
    @keyframes pulse-dot {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.4; }}
    }}

    .status-dot {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
    }}

    .status-dot.active {{
        background: #22c55e;
        animation: pulse-dot 2s ease-in-out infinite;
    }}

    .status-dot.inactive {{
        background: #94a3b8;
    }}

    .status-dot.warning {{
        background: #f59e0b;
        animation: pulse-dot 1.5s ease-in-out infinite;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Data table refinements
       ═══════════════════════════════════════════════════════════════════ */
    div[data-testid="stDataFrame"] {{
        font-size: 0.85rem;
    }}

    div[data-testid="stDataFrame"] th {{
        font-weight: 600;
        color: {P['text']};
    }}
    
    /* Metric card change indicators */
    .metric-change {{ font-size: 12px; margin-top: 4px; font-weight: 500; }}
    .metric-change.up {{ color: #16a34a; }}
    .metric-change.down {{ color: #dc2626; }}
    
    /* Severity distribution legend */
    .severity-legend {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 8px 0 12px 0; }}
    .severity-legend .item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: #64748B; }}
    .severity-legend .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
    .severity-legend .dot.p0 {{ background: #dc2626; }}
    .severity-legend .dot.p1 {{ background: #ea580c; }}
    .severity-legend .dot.p2 {{ background: #ca8a04; }}
    .severity-legend .dot.p3 {{ background: #16a34a; }}

    /* Quick action buttons */
    .quick-action-btn {{ display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: 8px; border: 1px solid #e2e8f0; background: #f8fafc; cursor: pointer; }}
    .quick-action-btn:hover {{ border-color: #1565C0; background: #eef3fa; }}
    .quick-action-btn .action-icon {{ width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; }}
    .quick-action-btn .action-text {{ font-size: 13px; font-weight: 500; color: #1a1a2e; }}
    .quick-action-btn .action-sub {{ font-size: 11px; color: #64748B; margin-top: 1px; }}

    /* Platform distribution */
    .platform-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }}
    .platform-item {{ display: flex; align-items: center; gap: 10px; padding: 12px 14px; border-radius: 8px; background: #f8fafc; border: 1px solid #f0f2f5; }}
    .platform-item .pf-icon {{ width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; color: #fff; flex-shrink: 0; }}
    .platform-item .pf-info {{ flex: 1; }}
    .platform-item .pf-name {{ font-size: 13px; font-weight: 500; }}
    .platform-item .pf-count {{ font-size: 11px; color: #64748B; }}
    .platform-item .pf-bar-wrap {{ margin-top: 4px; height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; }}
    .platform-item .pf-bar-fill {{ height: 100%; border-radius: 2px; }}

    /* Sidebar cards */
    .sidebar-card {{ background: #fff; border-radius: 10px; padding: 16px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); margin-bottom: 12px; }}

    /* Task list items */
    .task-list {{ list-style: none; padding: 0; margin: 0; }}
    .task-list li {{ display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; border-bottom: 1px solid #f0f2f5; }}
    .task-list li:last-child {{ border-bottom: none; }}
    .task-label {{ flex: 1; }}
    .task-value {{ font-weight: 500; }}

    /* Status dots */
    .status-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }}
    .status-dot.pending {{ background: #f59e0b; }}
    .status-dot.done {{ background: #16a34a; }}
    .status-dot.urgent {{ background: #dc2626; }}

    /* Topbar row -- blue gradient on first columns row */
    div[data-testid="stHorizontalBlock"]:first-of-type {{
        background: linear-gradient(135deg, #0D47A1, #1565C0) !important;
        border-radius: 10px 10px 0 0 !important;
        padding: 0.3rem 1.5rem !important;
        gap: 0 !important;
        margin-bottom: 0 !important;
    }}
    /* Tab buttons styled as topbar tabs */
    div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"] {{
        background: transparent !important;
        color: #ffffff !important;
        font-weight: 500 !important;
        border: none !important;
        border-bottom: 3px solid #00ACC1 !important;
        border-radius: 0 !important;
        padding: 8px 14px !important;
        font-size: 14px !important;
        box-shadow: none !important;
    }}
    div[data-testid="stHorizontalBlock"]:first-of-type button[kind="secondary"] {{
        background: transparent !important;
        color: rgba(255,255,255,0.7) !important;
        font-weight: 400 !important;
        border: none !important;
        border-bottom: 3px solid transparent !important;
        border-radius: 0 !important;
        padding: 8px 14px !important;
        font-size: 14px !important;
        box-shadow: none !important;
    }}
    div[data-testid="stHorizontalBlock"]:first-of-type button[kind="secondary"]:hover {{
        color: #ffffff !important;
        border-bottom: 3px solid rgba(255,255,255,0.3) !important;
        background: transparent !important;
    }}
    /* Hide column gap in topbar */
    div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="column"] {{
        gap: 0 !important;
    }}
    /* Dashboard section title */
    .section-title {{
        font-size: 1.15rem;
        font-weight: 600;
        color: #1a1a2e;
        border-left: 3px solid #0D47A1;
        padding-left: 12px;
        margin: 1.2rem 0 0.8rem 0;
    }}
    
    /* Quick action cards */
    .quick-action-card {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s ease;
    }}
    .quick-action-card:hover {{
        border-color: #0D47A1;
        box-shadow: 0 2px 8px rgba(13,71,161,0.1);
        transform: translateY(-1px);
    }}
    
    /* Severity bar */
    .severity-bar {{
        display: flex;
        height: 28px;
        border-radius: 6px;
        overflow: hidden;
        margin: 8px 0 16px 0;
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




