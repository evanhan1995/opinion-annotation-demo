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
        "P0": "#dc2626",
        "P1": "#ea580c",
        "P2": "#ca8a04",
        "P3": "#16a34a",
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
    # Google Fonts: Noto Sans SC (Chinese) + Inter (Latin)
    st.markdown(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    css = f"""
    <style>
    /* ═══════════════════════════════════════════════════════════════════
       Base & Typography — 企业简洁字体层级
       ═══════════════════════════════════════════════════════════════════ */
    html {{
        font-size: {TYPOGRAPHY['base_size']};
    }}

    html, body, [class*="css"] {{
        font-family: "Noto Sans SC", "Inter",
                     "Microsoft YaHei", "PingFang SC",
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
        width: 340px !important;
        background-color: #fff;
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
        padding: 1.2rem 2rem 3rem 2rem;
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
        color: white !important;
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
    .status-dot.pending {{ background: #f59e0b; }}
    .status-dot.done {{ background: #16a34a; }}
    .status-dot.urgent {{ background: #dc2626; }}

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
    .severity-legend {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 8px 0 12px 0; }}
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
    .platform-item {{ display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 8px; background: #f8fafc; border: 1px solid #f0f2f5; }}
    .platform-item .pf-icon {{ width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; color: #fff; flex-shrink: 0; }}
    .platform-item .pf-info {{ flex: 1; }}
    .platform-item .pf-name {{ font-size: 13px; font-weight: 500; }}
    .platform-item .pf-count {{ font-size: 11px; color: #64748B; }}
    .platform-item .pf-bar-wrap {{ margin-top: 4px; height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; }}
    .platform-item .pf-bar-fill {{ height: 100%; border-radius: 2px; }}

    /* Sidebar cards */
    .sidebar-card {{ background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); margin-bottom: 16px; margin-left: 12px; }}

    /* Task list items */
    .task-list {{ list-style: none; padding: 0; margin: 0; }}
    .task-list li {{ display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; border-bottom: 1px solid #f0f2f5; }}
    .task-list li:last-child {{ border-bottom: none; }}
    .task-label {{ flex: 1; }}
    .task-value {{ font-weight: 500; }}

    /* ═══════════════════════════════════════════════════════════════════
       Topbar — blue gradient matching Figma mockup.
       Rendered as pure HTML (.topbar class) for reliable styling.
       ═══════════════════════════════════════════════════════════════════ */
    .topbar {{
        height: 56px;
        background: linear-gradient(135deg, #0D47A1 0%, #1565C0 100%);
        display: flex;
        align-items: center;
        padding: 0 32px;
        margin: -1.2rem -2rem 1.2rem -2rem;
        box-shadow: 0 2px 8px rgba(13,71,161,0.25);
        gap: 0;
    }}
    .topbar-logo {{
        color: #fff;
        font-size: 18px;
        font-weight: 700;
        white-space: nowrap;
        margin-right: 32px;
    }}
    .topbar-logo span {{ color: #00ACC1; }}
    .topbar-tabs {{
        display: flex;
        align-items: center;
        height: 56px;
    }}
    .topbar-tab {{
        color: rgba(255,255,255,0.7) !important;
        font-size: 14px;
        font-weight: 500;
        padding: 0 16px;
        height: 56px;
        display: flex;
        align-items: center;
        text-decoration: none !important;
        white-space: nowrap;
        position: relative;
        transition: color 0.15s ease;
    }}
    .topbar-tab:hover {{
        color: rgba(255,255,255,0.9) !important;
    }}
    .topbar-tab.active {{
        color: #fff !important;
    }}
    .topbar-tab.active::after {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 12px;
        right: 12px;
        height: 3px;
        background: #00ACC1;
        border-radius: 3px 3px 0 0;
    }}
    .topbar-user {{
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 12px;
        color: rgba(255,255,255,0.8);
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

    /* Remove Streamlit column left-padding from first column in content rows. */
    section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div[data-testid="column"]:first-of-type {{
        padding-left: 0 !important;
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
        display: flex; height: 32px; border-radius: 6px; overflow: hidden; margin: 0 0 12px 0;
    }}
    .severity-bar .seg {{
        display: flex; align-items: center; justify-content: center;
        font-size: 12px; font-weight: 600; color: #fff; min-width: 48px;
    }}
    .severity-bar .seg.p0 {{ background: #dc2626; }}
    .severity-bar .seg.p1 {{ background: #ea580c; }}
    .severity-bar .seg.p2 {{ background: #ca8a04; }}
    .severity-bar .seg.p3 {{ background: #16a34a; }}

    /* ═══════════════════════════════════════════════════════════════════
       Dashboard — 总览仪表板 (Figma mockup page 2)
       ═══════════════════════════════════════════════════════════════════ */

    /* Page header */
    .page-header {{
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 24px;
    }}
    .page-header h1 {{
        font-size: 24px; font-weight: 700; color: #1a1a2e;
        border-bottom: none !important; padding-bottom: 0 !important;
        margin-top: 0 !important; margin-bottom: 0 !important;
        letter-spacing: 0 !important;
    }}
    .page-header .subtitle {{ font-size: 14px; color: #64748B; margin-top: 4px; }}
    .date-badge {{
        display: flex; align-items: center; gap: 8px;
        background: #fff; padding: 8px 16px; border-radius: 8px;
        font-size: 13px; color: #64748B;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}

    /* Metric cards — 4-column grid */
    .metric-card {{
        background: #fff; border-radius: 10px; padding: 20px 24px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }}
    .metric-card .label {{ font-size: 13px; color: #64748B; margin-bottom: 8px; font-weight: 500; }}
    .metric-card .value {{ font-size: 32px; font-weight: 700; color: #1a1a2e; line-height: 1.2; }}
    .metric-card .change {{ font-size: 12px; margin-top: 6px; }}
    .metric-card .change.up {{ color: #16a34a; }}
    .metric-card .change.down {{ color: #dc2626; }}
    .metric-card.highlight .value {{ color: #0D47A1; }}
    .metric-card.warn .value {{ color: #e65100; }}
    .metric-card.accent .value {{ color: #00ACC1; }}

    /* Generic card */
    .card {{
        background: #fff; border-radius: 10px; padding: 20px 24px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06); margin-bottom: 16px;
    }}
    .card-title {{ font-size: 15px; font-weight: 600; color: #1a1a2e; margin-bottom: 16px; }}

    /* Quick action buttons — Streamlit st.button() with use_container_width=True.
       Cannot be wrapped in custom HTML, so default Streamlit button styling applies. */

    /* Figma-style outline button (non-interactive HTML button) */
    .btn-outline-figma {{
        background: #fff; border: 1px solid #d0d5dd; color: #1a1a2e;
        padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 500;
        cursor: pointer; font-family: inherit;
    }}
    .btn-outline-figma:hover {{ border-color: #1565C0; color: #1565C0; }}

    /* Sidebar list */
    .sidebar-list {{ list-style: none; padding: 0; margin: 0; }}
    .sidebar-list li {{
        display: flex; justify-content: space-between;
        padding: 8px 0; font-size: 13px; border-bottom: 1px solid #f0f2f5;
    }}
    .sidebar-list li:last-child {{ border-bottom: none; }}
    .sidebar-list .val {{ font-weight: 500; }}

    /* Task items (今日动态) */
    .task-item {{
        display: flex; align-items: center; gap: 10px; padding: 8px 0;
        border-bottom: 1px solid #f0f2f5; font-size: 13px;
    }}
    .task-item:last-child {{ border-bottom: none; }}
    .task-item .status-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}

    /* Badge */
    .badge.orange {{ background: #fef0e6; color: #e65100; }}
    .badge.blue  {{ background: #e3edf9; color: #0D47A1; }}
    .badge.green {{ background: #dcfce7; color: #16a34a; }}

    /* Sidebar card heading */
    .sidebar-card h3 {{
        font-size: 14px; font-weight: 600; margin-bottom: 14px;
        display: flex; align-items: center; gap: 8px;
    }}
    .sidebar-card h3 .badge {{
        font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 500;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Entry & Annotation page (Figma page 3)
       ═══════════════════════════════════════════════════════════════════ */
    .section-label {{
        font-size: 13px; font-weight: 500; color: #64748B; margin-bottom: 8px;
    }}
    .url-row {{ display: flex; gap: 10px; margin-bottom: 16px; }}
    .url-input {{
        flex: 1; padding: 10px 14px; border: 1px solid #d0d5dd;
        border-radius: 8px; font-size: 14px; font-family: inherit; outline: none;
    }}
    .url-input:focus {{ border-color: #1565C0; box-shadow: 0 0 0 3px rgba(13,71,161,0.1); }}

    .data-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }}
    .data-item {{
        text-align: center; padding: 12px; background: #f8fafc;
        border-radius: 8px; border: 1px solid #f0f2f5;
    }}
    .data-item .val {{ font-size: 18px; font-weight: 700; color: #0D47A1; }}
    .data-item .lbl {{ font-size: 11px; color: #64748B; margin-top: 4px; }}

    .classify-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
    .classify-item .lbl {{ font-size: 12px; color: #64748B; margin-bottom: 6px; font-weight: 500; }}

    .tag-row {{ display: flex; gap: 6px; flex-wrap: wrap; }}
    .tag {{
        padding: 4px 12px; border-radius: 14px; font-size: 12px; font-weight: 500;
        cursor: pointer; border: 1px solid #e2e8f0; background: #fff;
        color: #64748B; display: inline-block; text-decoration: none;
        transition: all 0.15s ease;
    }}
    .tag:hover {{ border-color: #1565C0; color: #1565C0; }}
    .tag.active {{ border-color: #0D47A1; background: #e3edf9; color: #0D47A1; }}
    .tag.green {{ border-color: #16a34a; color: #16a34a; }}
    .tag.orange {{ border-color: #ea580c; color: #ea580c; }}
    .tag.red {{ border-color: #dc2626; color: #dc2626; }}

    .textarea {{
        width: 100%; padding: 10px 14px; border: 1px solid #d0d5dd;
        border-radius: 8px; font-size: 14px; font-family: inherit; outline: none;
        resize: vertical; min-height: 100px;
    }}
    .textarea:focus {{ border-color: #1565C0; box-shadow: 0 0 0 3px rgba(13,71,161,0.1); }}

    .action-bar {{ display: flex; gap: 10px; justify-content: flex-end; margin-top: 16px; }}

    .result-card {{
        background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
        padding: 16px 20px; border-left: 4px solid #0D47A1; margin-bottom: 12px;
    }}
    .result-card .r-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
    .result-card .r-title {{ font-size: 14px; font-weight: 600; }}
    .result-card .r-tag {{ font-size: 11px; padding: 2px 10px; border-radius: 10px; }}
    .result-card .r-body {{ font-size: 13px; color: #64748B; line-height: 1.6; }}
    .result-card .r-info {{ display: flex; gap: 16px; margin-top: 8px; font-size: 12px; color: #64748B; flex-wrap: wrap; }}

    /* ═══════════════════════════════════════════════════════════════════
       Monitor dashboard (Figma page 4)
       ═══════════════════════════════════════════════════════════════════ */
    .keyword-bar {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
    .keyword-input {{
        flex: 1; min-width: 200px; padding: 8px 12px; border: 1px solid #d0d5dd;
        border-radius: 8px; font-size: 13px; font-family: inherit; outline: none;
    }}
    .keyword-input:focus {{ border-color: #1565C0; }}
    .keyword-tag {{
        display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px;
        background: #e3edf9; color: #0D47A1; border-radius: 14px; font-size: 12px;
        margin: 2px;
    }}
    .keyword-tag .remove {{ cursor: pointer; font-size: 14px; opacity: 0.6; }}
    .keyword-tag .remove:hover {{ opacity: 1; }}

    .platform-select {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px; }}
    .platform-opt {{
        padding: 4px 12px; border: 1px solid #e2e8f0; border-radius: 14px;
        font-size: 12px; cursor: pointer; background: #fff; color: #64748B;
        display: inline-block; transition: all 0.15s ease;
    }}
    .platform-opt:hover {{ border-color: #1565C0; color: #1565C0; }}
    .platform-opt.active {{ background: #0D47A1; color: #fff; border-color: #0D47A1; }}

    .indicator-row {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }}
    .indicator-item {{
        text-align: center; padding: 16px; background: #f8fafc;
        border-radius: 8px; border: 1px solid #f0f2f5;
    }}
    .indicator-item .val {{ font-size: 24px; font-weight: 700; color: #0D47A1; }}
    .indicator-item .lbl {{ font-size: 12px; color: #64748B; margin-top: 4px; }}

    .filter-bar {{ display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
    .filter-bar .date-input {{
        padding: 6px 12px; border: 1px solid #d0d5dd; border-radius: 6px;
        font-size: 13px; font-family: inherit;
    }}

    .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .data-table th {{
        text-align: left; padding: 10px 12px; background: #f8fafc; color: #64748B;
        font-weight: 500; border-bottom: 2px solid #e2e8f0;
    }}
    .data-table td {{
        padding: 10px 12px; border-bottom: 1px solid #f0f2f5;
    }}
    .data-table tr:hover td {{ background: #f8fafc; }}

    .status-badge {{
        display: inline-block; padding: 2px 10px; border-radius: 10px;
        font-size: 11px; font-weight: 500;
    }}
    .status-badge.new {{ background: #fde8e8; color: #dc2626; }}
    .status-badge.processing {{ background: #fef0e6; color: #ea580c; }}
    .status-badge.done {{ background: #dcfce7; color: #16a34a; }}
    .status-badge.pending {{ background: #fef9c3; color: #a16207; }}

    .severity-dot {{
        display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px;
    }}
    .severity-dot.p0 {{ background: #dc2626; }}
    .severity-dot.p1 {{ background: #ea580c; }}
    .severity-dot.p2 {{ background: #ca8a04; }}
    .severity-dot.p3 {{ background: #16a34a; }}

    .pagination {{
        display: flex; justify-content: space-between; align-items: center;
        margin-top: 16px; font-size: 13px; color: #64748B;
    }}
    .pagination .page-btns {{ display: flex; gap: 4px; }}
    .pagination .page-btns span {{
        padding: 4px 10px; border: 1px solid #e2e8f0; border-radius: 4px; cursor: pointer;
    }}
    .pagination .page-btns span.active {{
        background: #0D47A1; color: #fff; border-color: #0D47A1;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       Knowledge base (Figma page 5)
       ═══════════════════════════════════════════════════════════════════ */
    .kb-layout {{ display: flex; gap: 24px; }}
    .kb-left-panel {{ width: 300px; flex-shrink: 0; }}
    .kb-content-panel {{ flex: 1; min-width: 0; }}

    .search-wrap {{
        position: relative; margin-bottom: 16px;
    }}
    .search-wrap .search-icon {{
        position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #64748B; font-size: 14px;
    }}

    .tree-node {{ padding: 2px 0; }}
    .tree-header {{
        display: flex; align-items: center; gap: 6px; padding: 6px 8px;
        border-radius: 6px; font-size: 13px; cursor: pointer; color: #1a1a2e;
        transition: background 0.15s ease;
    }}
    .tree-header:hover {{ background: #f0f2f5; }}
    .tree-header.active {{ background: #e3edf9; color: #0D47A1; font-weight: 500; }}
    .tree-header .count {{
        font-size: 11px; color: #64748B; margin-left: auto;
    }}
    .tree-children {{ padding-left: 20px; }}

    .conversation-area {{
        min-height: 320px; display: flex; flex-direction: column;
    }}
    .msg-list {{
        flex: 1; display: flex; flex-direction: column; gap: 12px;
        padding: 12px 0; max-height: 380px; overflow-y: auto;
    }}
    .msg {{
        padding: 10px 14px; border-radius: 10px; max-width: 85%; font-size: 13px; line-height: 1.5;
    }}
    .msg.ai {{
        background: #f0f5ff; border: 1px solid #dce5f5; align-self: flex-start;
    }}
    .msg.user {{
        background: #0D47A1; color: #fff; align-self: flex-end;
    }}

    .knowledge-content {{ }}
    .kc-header {{
        display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;
    }}
    .kc-title {{ font-size: 18px; font-weight: 600; }}
    .kc-meta {{ font-size: 12px; color: #64748B; margin-top: 4px; }}
    .kc-body {{
        font-size: 14px; line-height: 1.8; color: #334155;
    }}
    .kc-body h4 {{
        font-size: 15px; font-weight: 600; margin: 16px 0 8px; color: #1a1a2e;
    }}
    .kc-body p {{ margin-bottom: 12px; }}
    .kc-body ul {{ padding-left: 20px; margin-bottom: 12px; }}
    .kc-body li {{ margin-bottom: 4px; }}
    .kc-tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }}

    .tag.blue {{ background: #e3edf9; color: #0D47A1; }}
    .tag.green {{ background: #dcfce7; color: #16a34a; }}
    .tag.orange {{ background: #fef0e6; color: #e65100; }}

    /* ═══════════════════════════════════════════════════════════════════
       Sidebar (Figma page 6)
       ═══════════════════════════════════════════════════════════════════ */
    .sidebar-header {{
        background: linear-gradient(135deg, #0D47A1, #1565C0); padding: 20px 24px; color: #fff;
        margin: -1rem -1rem 0 -1rem;
    }}
    .sidebar-header h2 {{
        font-size: 16px; font-weight: 600; color: #fff; border: none; padding: 0; margin: 0;
        display: flex; align-items: center; gap: 8px;
    }}
    .sidebar-header .sub {{
        font-size: 12px; opacity: 0.7; margin-top: 4px; color: rgba(255,255,255,0.8);
    }}
    .section-title {{
        font-size: 12px; font-weight: 600; color: #64748B; text-transform: uppercase;
        letter-spacing: 0.5px; margin-bottom: 8px; padding: 0 8px;
    }}
    .sys-status {{
        display: flex; align-items: center; gap: 8px; padding: 10px 14px;
        background: #f8fafc; border-radius: 8px; margin-bottom: 6px;
    }}
    .sys-status .dot {{
        width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
    }}
    .sys-status .dot.green {{ background: #16a34a; }}
    .sys-status .dot.yellow {{ background: #f59e0b; }}
    .sys-status .dot.red {{ background: #dc2626; }}
    .sys-status .label {{
        font-size: 13px; font-weight: 500; flex: 1;
    }}
    .sys-status .value {{
        font-size: 12px; color: #64748B;
    }}
    .sidebar-menu-item {{
        display: flex; align-items: center; gap: 10px; padding: 10px 12px;
        border-radius: 8px; cursor: pointer; font-size: 13px; transition: all 0.15s;
        color: #1a1a2e; text-decoration: none;
    }}
    .sidebar-menu-item:hover {{ background: #f0f2f5; }}
    .sidebar-menu-item .m-icon {{
        width: 28px; height: 28px; border-radius: 6px; display: flex;
        align-items: center; justify-content: center; font-size: 14px;
    }}
    .sidebar-menu-item .m-icon.blue {{ background: #e3edf9; }}
    .sidebar-menu-item .m-icon.teal {{ background: #e0f4f6; }}
    .sidebar-menu-item .badge {{
        margin-left: auto; background: #fde8e8; color: #dc2626;
        padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 500;
    }}
    .auto-control {{
        background: #f8fafc; border-radius: 10px; padding: 14px; border: 1px solid #e2e8f0;
    }}
    .control-row {{
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 12px;
    }}
    .control-row:last-child {{ margin-bottom: 0; }}
    .control-label {{
        font-size: 13px;
    }}
    .control-label .sub {{
        font-size: 11px; color: #64748B; display: block;
    }}
    .pipeline-step {{
        display: flex; align-items: center; gap: 10px; padding: 8px 0;
        border-bottom: 1px solid #f0f2f5;
    }}
    .pipeline-step:last-child {{ border-bottom: none; }}
    .pipeline-step .step-icon {{
        width: 24px; height: 24px; border-radius: 50%; display: flex;
        align-items: center; justify-content: center; font-size: 11px;
        font-weight: 600; color: #fff; flex-shrink: 0;
    }}
    .step-icon.done {{ background: #16a34a; }}
    .step-icon.progress {{ background: #1565C0; }}
    .step-icon.pending {{ background: #d0d5dd; }}
    .pipeline-step .step-info {{ flex: 1; }}
    .pipeline-step .step-name {{ font-size: 13px; }}
    .pipeline-step .step-status {{ font-size: 11px; color: #64748B; }}
    .pipeline-step .step-time {{ font-size: 11px; color: #64748B; }}
    .login-status {{ }}
    .login-item {{
        display: flex; align-items: center; gap: 10px; padding: 8px 12px;
        border-radius: 8px; background: #f8fafc; margin-bottom: 6px;
    }}
    .login-item .login-dot {{
        width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
    }}
    .login-dot.active {{ background: #16a34a; }}
    .login-dot.error {{ background: #dc2626; }}
    .login-dot.idle {{ background: #d0d5dd; }}
    .login-item .pname {{ font-size: 13px; flex: 1; }}
    .login-item .pstatus {{ font-size: 11px; color: #64748B; }}


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




