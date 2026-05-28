# -*- coding: utf-8 -*-
"""舆情智能标注系统 —— Web 界面

使用方法:
    streamlit run app.py
    然后在浏览器中打开 http://localhost:8501
"""

import sys
import time
from pathlib import Path

# 路径设置（确保能 import engine 模块）
PROJECT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = PROJECT_DIR / "engine"
OUTPUT_DIR = PROJECT_DIR / "outputs"
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR.parent / "shared"))
sys.path.insert(0, str(PROJECT_DIR.parent))

import streamlit as st
from engine.scraper import SCRAPERS

from ui.theme import inject_css
from ui.sidebar import render_sidebar
from ui.tab_entry import render_tab_entry
from ui.tab3_monitor import render_tab3
from ui.tab4_disposition import render_tab4
from ui.tab_knowledge import render_tab_knowledge
from ui.tab6_reports import render_tab6
from ui.tab_tracking import render_tab_tracking

# Startup sanity check: verify all scrapers importable
_supported = list(SCRAPERS.keys())
print(f"[Scraper] Supported platforms: {_supported}")
if "小红书" not in _supported:
    print("[Scraper] WARNING: XHS scraper NOT loaded! Restart Streamlit after updating code.")


# ── Scheduler background thread ────────────────────────────────────────
@st.cache_resource
def _start_scheduler():
    """Start the background scheduler thread once per session."""
    from scheduler import SchedulerThread, get_scheduler_status
    t = SchedulerThread()
    t.start()
    return t


_scheduler = _start_scheduler()


# ── Tracking scheduler background thread ──────────────────────────────
@st.cache_resource
def _start_tracking_scheduler():
    """Start the background tracking scheduler thread once per session."""
    from engine.tracker import TrackingScheduler
    t = TrackingScheduler()
    t.start()
    return t


_tracking_scheduler = _start_tracking_scheduler()

# ═══════════════════════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="舆情智能标注系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

# ═══════════════════════════════════════════════════════════════════════════════
# Authentication gate
# ═══════════════════════════════════════════════════════════════════════════════

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    from ui.login import render_login_page
    render_login_page()
    st.stop()

st.title("舆情智能标注系统")
st.caption("基于 Wiki 知识库 + LLM 的智能打标与分流判断")

# ═══════════════════════════════════════════════════════════════════════════════
# 初始化 session state
# ═══════════════════════════════════════════════════════════════════════════════

for key, default in [
    ("scraped_data", None),
    ("annotation_result", None),
    ("correction_result", None),
    ("ingest_result", None),
    ("agent_messages", []),
    ("system_prompt_loaded", False),
    ("kb_stats", None),
    ("config", None),
    ("demo_guide_shown", False),
    ("kb_authenticated", False),
    ("_result_source", ""),
    ("monitor_harvest", None),
    ("p0p1_alerts", []),
    ("pipeline_init", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

_patrol_pending = st.session_state.pop("_patrol_pending", False)

# Initialize pipeline module on first load
if not st.session_state.pipeline_init:
    from pipeline import reset_pipeline
    reset_pipeline()
    st.session_state.pipeline_init = True

# Demo guide: show once per session
if not st.session_state.demo_guide_shown and not st.session_state.annotation_result:
    with st.expander("👋 快速入门指南", expanded=True):
        st.markdown("""
        1. **Monitor** → 「📡 Monitor」关键词巡检
        2. **录入研判** → 「📝 录入研判」粘贴链接抓取标注，或手动录入
        3. **案例处置** → 「📋 案例处置」查看和更新案例状态
        4. **知识库** → 「📚 知识库」浏览知识库 + 管理员AI问答
        5. **报告** → 「📊 报告」查看日报和月报
        6. **高危追踪** → 「⚠️ 高危追踪」持续监控高风险舆情流量变化
        7. **流水线** → 侧边栏「🔁 自动化流水线」一键执行全流程
        """)
        if st.button("知道了，开始使用", key="dismiss_guide"):
            st.session_state.demo_guide_shown = True
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════════════════════════════════════

render_sidebar(_patrol_pending)

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 布局 — uses st.radio (key="active_tab") instead of st.tabs() so the
# selected tab survives st.rerun(). st.tabs() loses tab state on full-script
# rerun because its internal widget key is opaque; radio stores it explicitly.
# ═══════════════════════════════════════════════════════════════════════════════

# Build role-filtered tab list
user_role = st.session_state.get("user", {}).get("role", "admin")
from engine.auth import get_allowed_tabs
TAB_LABELS = get_allowed_tabs(user_role)
if "active_tab" not in st.session_state or st.session_state.active_tab not in TAB_LABELS:
    st.session_state.active_tab = TAB_LABELS[0]

# Handle deferred tab switches (e.g. from citation button "查看 case")
if st.session_state.get("_pending_tab"):
    pending = st.session_state.pop("_pending_tab")
    # Map old tab names to new ones
    _tab_map = {
        "📚 知识库": "📚 知识库",
        "💬 扫地僧": "📚 知识库",  # merged
    }
    st.session_state.active_tab = _tab_map.get(pending, pending)

# Styled button-bar tab navigation (replaces st.radio for visual polish)
active_tab = st.session_state.active_tab
tab_cols = st.columns(len(TAB_LABELS))
for i, label in enumerate(TAB_LABELS):
    with tab_cols[i]:
        if st.button(
            label, key=f"nav_{label}", use_container_width=True,
            type="primary" if active_tab == label else "secondary",
        ):
            st.session_state.active_tab = label
            st.rerun()
active_tab = st.session_state.active_tab  # may have changed from button click


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline lock: block tab interactions while pipeline is running
# ═══════════════════════════════════════════════════════════════════════════════

from pipeline import get_pipeline_status as _get_pipeline_status
from pipeline import force_reset_pipeline as _force_reset_pipeline
from datetime import datetime as _dt
_pipeline_running = _get_pipeline_status().get("is_running", False)

if _pipeline_running:
    pstat = _get_pipeline_status()
    # Check if pipeline has been running suspiciously long (>10 min)
    started = pstat.get("started_at", "")
    running_too_long = False
    if started:
        try:
            elapsed = (_dt.now() - _dt.fromisoformat(started)).total_seconds()
            running_too_long = elapsed > 600  # 10 min threshold
        except Exception:
            pass

    if running_too_long:
        st.error("⚠️ 流水线已运行超过 10 分钟，可能已卡死。")
        if st.button("🔧 强制重置流水线", type="primary", key="force_reset_pipeline"):
            _force_reset_pipeline()
            st.success("流水线已强制重置，页面即将刷新...")
            time.sleep(1.5)
            st.rerun()
    else:
        st.warning("🔁 自动化流水线正在执行中，操作面板暂时锁定。请等待完成或查看侧边栏进度。")

    step_cols = st.columns(len(pstat.get("steps", [])))
    for i, step in enumerate(pstat.get("steps", [])):
        s = step["status"]
        icon = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}.get(s, "⏳")
        with step_cols[i]:
            st.caption(f"{icon} {step['label']}")
            if s == "running":
                st.progress(step.get("progress", 0) or 0.0)
                if step.get("details"):
                    st.caption(step["details"][:40])
            elif s == "done":
                st.caption("完成")
            elif s == "error":
                st.caption(f"错误: {step.get('error', '')[:30]}")
    if pstat.get("errors"):
        for e in pstat["errors"][-3:]:
            st.caption(f"⚠️ {e[:100]}")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# Tab routing — match by label string, not index (TAB_LABELS varies by role)
# ═══════════════════════════════════════════════════════════════════════════════

if active_tab == "📊 总览":
    _render_overview()
elif active_tab == "📡 Monitor":
    render_tab3()
elif active_tab == "📝 录入研判":
    render_tab_entry()
elif active_tab == "📋 案例处置":
    render_tab4()
elif active_tab == "📚 知识库":
    render_tab_knowledge()
elif active_tab == "📊 报告":
    render_tab6()
elif active_tab == "⚠️ 高危追踪":
    render_tab_tracking()

# ═══════════════════════════════════════════════════════════════════════════════
# Overview dashboard
# ═══════════════════════════════════════════════════════════════════════════════


def _render_overview():
    """Render the overview dashboard — aggregate metrics and quick actions."""
    st.subheader("📊 总览仪表板")

    try:
        from agents.curator import query_stats
        stats = query_stats()
    except Exception:
        stats = None

    if not stats or stats.get("total_cases", 0) == 0:
        st.info("系统尚未积累足够数据。请先运行 Monitor 巡检或录入案例。")
        st.markdown("**快捷开始:**")
        qs1, qs2 = st.columns(2)
        with qs1:
            if st.button("📡 执行 Monitor 巡检", use_container_width=True, key="ov_empty_monitor"):
                st.session_state.active_tab = "📡 Monitor"
                st.rerun()
        with qs2:
            if st.button("📝 录入新案例", use_container_width=True, key="ov_empty_entry"):
                st.session_state.active_tab = "📝 录入研判"
                st.rerun()
        return

    sev = stats.get("severity_dist", {})
    plat = stats.get("platform_dist", {})
    status_dist = stats.get("status_dist", {})
    total = stats.get("total_cases", 0)

    # Row 1: Key metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("总案例数", total)
    p0p1 = sev.get("P0", 0) + sev.get("P1", 0)
    m2.metric("高优待处理 (P0/P1)", p0p1, delta_color="inverse")
    m3.metric("覆盖平台", len(plat))
    pending = status_dist.get("待跟进", 0)
    m4.metric("待跟进案例", pending)

    # Row 2: Severity bar
    sev_total = sum(sev.values()) or 1
    sev_html_parts = []
    for level, color in [("P0", "#dc3545"), ("P1", "#fd7e14"), ("P2", "#ffc107"), ("P3", "#28a745")]:
        cnt = sev.get(level, 0)
        if cnt:
            pct = cnt / sev_total * 100
            sev_html_parts.append(
                f"<div style='width:{pct}%;background:{color};display:flex;"
                f"align-items:center;justify-content:center;font-size:11px;"
                f"color:white;padding:2px 0;'>{level}: {cnt}</div>"
            )
    if sev_html_parts:
        st.markdown(
            f"<div style='display:flex;height:28px;border-radius:4px;"
            f"overflow:hidden;margin:8px 0 16px 0;'>"
            + "".join(sev_html_parts)
            + "</div>",
            unsafe_allow_html=True,
        )

    # Row 3: Quick actions
    st.caption("快捷操作")
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        if st.button("🔍 Monitor 巡检", use_container_width=True, key="ov_monitor"):
            st.session_state.active_tab = "📡 Monitor"
            st.rerun()
    with q2:
        if st.button("📝 录入新案例", use_container_width=True, key="ov_entry"):
            st.session_state.active_tab = "📝 录入研判"
            st.rerun()
    with q3:
        if st.button("📋 案例处置", use_container_width=True, key="ov_dispo"):
            st.session_state.active_tab = "📋 案例处置"
            st.rerun()
    with q4:
        if st.button("⚠️ 高危追踪", use_container_width=True, key="ov_track"):
            st.session_state.active_tab = "⚠️ 高危追踪"
            st.rerun()

    # Row 4: Platform distribution
    if plat:
        st.divider()
        st.caption("平台分布")
        plat_cols = st.columns(len(plat))
        for i, (pf, cnt) in enumerate(sorted(plat.items(), key=lambda x: -x[1])):
            with plat_cols[i]:
                st.metric(pf, cnt)


# ═══════════════════════════════════════════════════════════════════════════════
# 显式重跑：确保标注完成后页面刷新到最新结果
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state.get("_needs_rerun"):
    st.session_state._needs_rerun = False
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# 页脚
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.caption("舆情智能标注系统 | 基于 Wiki 知识库 + 案例驱动迭代 | DeepSeek / Claude / OpenAI 多 Provider 支持")
