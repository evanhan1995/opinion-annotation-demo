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
from ui.tab_settings import render_tab_settings

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
    ("entry_queue", []),
    ("batch_auto_process", False),
    ("batch_items", []),
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
TAB_LABELS = ["📊 总览", "📡 Monitor", "📝 录入研判", "📋 案例处置", "📚 知识库", "📊 报告", "⚠️ 高危追踪", "⚙️ 设置"]


# Topbar with integrated tabs (st.columns + st.buttons)
if "active_tab" not in st.session_state:
    st.session_state.active_tab = TAB_LABELS[0]
active_tab = st.session_state.active_tab
_logo_col, *tab_cols, _user_col = st.columns([1.5] + [1] * 8 + [1.5])
with _logo_col:
    st.markdown('<span style="color:#fff;font-size:17px;font-weight:700;white-space:nowrap;">📊 舆情智能标注 <span style="color:#00ACC1;">|</span> OPS</span>', unsafe_allow_html=True)
for _i, _label in enumerate(TAB_LABELS):
    with tab_cols[_i]:
        is_active = _label == active_tab
        if st.button(_label, key=f"nav_{_label}", type="primary" if is_active else "secondary", use_container_width=True):
            st.session_state.active_tab = _label
            st.rerun()
with _user_col:
    st.markdown('<div style="display:flex;align-items:center;gap:8px;color:#fff;font-size:13px;justify-content:flex-end;"><span>管理员</span><div style="width:32px;height:32px;border-radius:50%;background:#00ACC1;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600;color:#fff;">管</div></div>', unsafe_allow_html=True)


_tid = int(st.query_params.get('tab', '0'))
_rtab = TAB_LABELS[_tid] if 0 <= _tid < len(TAB_LABELS) else TAB_LABELS[0]
if "active_tab" not in st.session_state or _rtab != st.session_state.active_tab:
    st.session_state.active_tab = _rtab

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

# Styled button-bar tab navigation (desktop tab style)
active_tab = st.session_state.active_tab
# Tab switching -- radio styled as integrated topbar tabs
curr_idx = TAB_LABELS.index(st.session_state.active_tab) if st.session_state.active_tab in TAB_LABELS else 0
st.markdown('</div>', unsafe_allow_html=True)


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
# Overview dashboard (must be defined before tab routing below)
# ═══════════════════════════════════════════════════════════════════════════════


def _render_overview():
    """Render the overview dashboard matching the HTML design mockup."""

    try:
        from agents.curator import query_stats
        stats = query_stats()
    except Exception:
        stats = None

    if not stats or stats.get('total_cases', 0) == 0:
        st.markdown('<p class=\"section-title\">📊 总览仪表板</p>', unsafe_allow_html=True)
        st.info('系统尚未积累足够数据。请先运行 Monitor 巡检或录入案例。')
        qs1, qs2 = st.columns(2)
        with qs1:
            if st.button('📡 执行 Monitor 巡检', use_container_width=True, key='ov_empty_monitor'):
                st.session_state.active_tab = '📡 Monitor'
                st.rerun()
        with qs2:
            if st.button('📝 录入新案例', use_container_width=True, key='ov_empty_entry'):
                st.session_state.active_tab = '📝 录入研判'
                st.rerun()
        return

    sev = stats.get('severity_dist', {})
    plat = stats.get('platform_dist', {})
    status_dist = stats.get('status_dist', {})
    total = stats.get('total_cases', 0)
    p0p1 = sev.get('P0', 0) + sev.get('P1', 0)
    pending = status_dist.get('待跟进', 0)
    max_cnt = max(plat.values()) if plat else 1

    # === LAYOUT: main content + right sidebar ===
    main_col, side_col = st.columns([3, 1])

    with main_col:
        # Page header
        st.markdown(
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">'
            + '<h1 style="font-size:24px;font-weight:700;color:#1a1a2e;margin:0;border:none;padding:0;">总览仪表板</h1>'
            + '<div style="display:flex;align-items:center;gap:8px;background:#fff;padding:8px 16px;border-radius:8px;font-size:13px;color:#64748B;box-shadow:0 1px 3px rgba(0,0,0,0.06);">📅 2026-06-23 · 最近7天</div>'
            + '</div>', unsafe_allow_html=True
        )

        # Metric cards (4 in a row with delta)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric('📋 总案例数', total, '↑ 较上周 +12.5%')
        with m2:
            st.metric('🚨 高优待处理 P0/P1', p0p1, f'较昨日 +{p0p1}', delta_color='inverse')
        with m3:
            st.metric('🌐 覆盖平台', len(plat), '小红书 · 抖音 · 微博')
        with m4:
            st.metric('📌 待跟进案例', pending, f'{pending} 条待处理', delta_color='inverse')

        # Two-column: severity + quick actions
        lcol, rcol = st.columns(2)
        with lcol:
            st.markdown('<div style="background:#fff;border-radius:10px;padding:20px 24px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">', unsafe_allow_html=True)
            st.markdown('<p style="font-size:15px;font-weight:600;color:#1a1a2e;margin:0 0 16px 0;">⚠️ 严重度分布</p>', unsafe_allow_html=True)

            sev_total = sum(sev.values()) or 1
            parts = []
            for level, color, label in [('P0', '#dc2626', 'P0'), ('P1', '#ea580c', 'P1'), ('P2', '#ca8a04', 'P2'), ('P3', '#16a34a', 'P3')]:
                cnt = sev.get(level, 0)
                if cnt:
                    pct = cnt / sev_total * 100
                    parts.append(f'<div class=\"seg\" style=\"flex:{int(pct)};background:{color};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:#fff;min-width:40px;\">{level}</div>')
            if parts:
                st.markdown('<div class=\"severity-bar\" style=\"display:flex;height:32px;border-radius:6px;overflow:hidden;margin-bottom:12px;\">' + ''.join(parts) + '</div>', unsafe_allow_html=True)

            # Legend
            c_map = {'P0': '#dc2626', 'P1': '#ea580c', 'P2': '#ca8a04', 'P3': '#16a34a'}
            legend = []
            for level in ['P0', 'P1', 'P2', 'P3']:
                cnt = sev.get(level, 0)
                if cnt:
                    dot = '<span style="width:10px;height:10px;border-radius:50%;background:' + c_map[level] + ';display:inline-block;"></span>'
                    legend.append('<span style="display:flex;align-items:center;gap:6px;font-size:12px;color:#64748B;">' + dot + level + ': ' + str(cnt) + ' 条</span>')
            if legend:
                st.markdown('<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px;">' + ''.join(legend) + '</div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

        with rcol:
            st.markdown('<div style="background:#fff;border-radius:10px;padding:20px 24px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">', unsafe_allow_html=True)
            st.markdown('<p style="font-size:15px;font-weight:600;color:#1a1a2e;margin:0 0 16px 0;">⚡ 快捷操作</p>', unsafe_allow_html=True)

            actions = [('🔍', 'Monitor 巡检', '启动新一轮巡检', '#e3edf9'), ('📝', '录入新案例', '手动录入舆情案例', '#e0f4f6'), ('⚡', '案例处置', '待处理 12 条', '#fef0e6'), ('🏴', '高危追踪', '高优跟进 8 条', '#fde8e8')]
            for icon, text, sub, bg in actions:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#f8fafc;margin-bottom:8px;cursor:pointer;">'
                    + f'<div style="width:36px;height:36px;border-radius:8px;background:{bg};display:flex;align-items:center;justify-content:center;font-size:18px;">{icon}</div>'
                    + f'<div><div style="font-size:13px;font-weight:500;color:#1a1a2e;">{text}</div><div style="font-size:11px;color:#64748B;">{sub}</div></div>'
                    + '</div>', unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

        # Platform distribution
        if plat:
            st.markdown('<div style="background:#fff;border-radius:10px;padding:20px 24px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">', unsafe_allow_html=True)
            st.markdown('<p style="font-size:15px;font-weight:600;color:#1a1a2e;margin:0 0 16px 0;">🌐 平台分布</p>', unsafe_allow_html=True)

            plat_colors = {'小红书': {'bg': '#ff2442', 'abbr': '红'}, '抖音': {'bg': '#1e1e1e', 'abbr': '抖'}, 'YouTube': {'bg': '#ff0000', 'abbr': 'YT'}, '微博': {'bg': '#e6162d', 'abbr': '微'}, 'B站': {'bg': '#fb7299', 'abbr': 'B'}, '公众号': {'bg': '#07c160', 'abbr': '公'}}

            for pf, cnt in sorted(plat.items(), key=lambda x: -x[1]):
                info = plat_colors.get(pf, {'bg': '#64748B', 'abbr': pf[:2]})
                pct = (cnt / max_cnt * 100) if max_cnt > 0 else 0
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;background:#f8fafc;border:1px solid #f0f2f5;margin-bottom:8px;">'
                    + f'<div style="width:32px;height:32px;border-radius:6px;background:{info["bg"]};display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600;color:#fff;flex-shrink:0;">{info["abbr"]}</div>'
                    + f'<div style="flex:1;"><div style="font-size:13px;font-weight:500;">{pf}</div>'
                    + f'<div style="font-size:11px;color:#64748B;">{cnt} 条</div>'
                    + f'<div style="margin-top:4px;height:4px;background:#e2e8f0;border-radius:2px;overflow:hidden;"><div style="height:100%;border-radius:2px;width:{pct:.0f}%;background:{info["bg"]};"></div></div>'
                    + '</div></div>', unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

    with side_col:
        # Task count
        st.markdown(
            f'<div style="background:#fff;border-radius:10px;padding:16px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.06);margin-bottom:12px;">'
            + '<p style="font-size:14px;font-weight:600;margin:0 0 12px 0;display:flex;align-items:center;gap:8px;">⏰ 待处理任务'
            + f'<span style="font-size:10px;padding:2px 8px;border-radius:10px;font-weight:500;background:#fef0e6;color:#e65100;">{pending}</span></p>'
            + '<ul style="list-style:none;padding:0;margin:0;">'
            + '<li style="display:flex;justify-content:space-between;padding:8px 0;font-size:13px;border-bottom:1px solid #f0f2f5;"><span>待标注案例</span><span style="font-weight:500;">12 条</span></li>'
            + '<li style="display:flex;justify-content:space-between;padding:8px 0;font-size:13px;border-bottom:1px solid #f0f2f5;"><span>待审核结果</span><span style="font-weight:500;">6 条</span></li>'
            + '<li style="display:flex;justify-content:space-between;padding:8px 0;font-size:13px;border-bottom:none;"><span>待跟进处置</span><span style="font-weight:500;">5 条</span></li>'
            + '</ul></div>', unsafe_allow_html=True
        )

        # Today's updates
        st.markdown(
            '<div style="background:#fff;border-radius:10px;padding:16px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.06);margin-bottom:12px;">'
            + '<p style="font-size:14px;font-weight:600;margin:0 0 12px 0;">📊 今日动态</p>'
            + '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;font-size:13px;border-bottom:1px solid #f0f2f5;"><span style="width:8px;height:8px;border-radius:50%;background:#dc2626;flex-shrink:0;"></span><span>抖音 P0 舆情爆发</span></div>'
            + '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;font-size:13px;border-bottom:1px solid #f0f2f5;"><span style="width:8px;height:8px;border-radius:50%;background:#f59e0b;flex-shrink:0;"></span><span>微博新案例待标注</span></div>'
            + '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;font-size:13px;border-bottom:1px solid #f0f2f5;"><span style="width:8px;height:8px;border-radius:50%;background:#f59e0b;flex-shrink:0;"></span><span>小红书巡检完成</span></div>'
            + '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;font-size:13px;border-bottom:none;"><span style="width:8px;height:8px;border-radius:50%;background:#16a34a;flex-shrink:0;"></span><span>B站案例处置完毕</span></div>'
            + '</div>', unsafe_allow_html=True
        )

        # System status
        st.markdown(
            '<div style="background:#fff;border-radius:10px;padding:16px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.06);margin-bottom:12px;">'
            + '<p style="font-size:14px;font-weight:600;margin:0 0 12px 0;">🔄 系统状态</p>'
            + '<ul style="list-style:none;padding:0;margin:0;">'
            + '<li style="display:flex;justify-content:space-between;padding:8px 0;font-size:13px;border-bottom:1px solid #f0f2f5;"><span>巡检服务</span><span style="color:#16a34a;font-weight:500;">● 运行中</span></li>'
            + '<li style="display:flex;justify-content:space-between;padding:8px 0;font-size:13px;border-bottom:1px solid #f0f2f5;"><span>标注队列</span><span style="color:#f59e0b;font-weight:500;">● 拥堵 3</span></li>'
            + '<li style="display:flex;justify-content:space-between;padding:8px 0;font-size:13px;border-bottom:none;"><span>数据网关</span><span style="color:#16a34a;font-weight:500;">● 正常</span></li>'
            + '</ul></div>', unsafe_allow_html=True
        )
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
elif active_tab == "⚙️ 设置":
    render_tab_settings()

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

