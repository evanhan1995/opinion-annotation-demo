# -*- coding: utf-8 -*-
"""舆情智能标注系统 —— Web 界面

使用方法:
    streamlit run app.py
    然后在浏览器中打开 http://localhost:8501
"""

import html
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
# Authentication gate
# ═══════════════════════════════════════════════════════════════════════════════

# ── Debug log helper ───────────────────────────────────────────────────
import datetime as _dt
def _dlog(msg):
    try:
        with open(PROJECT_DIR / "config" / "_debug.log", "a", encoding="utf-8") as _f:
            _f.write(f"{_dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]} {msg}\n")
    except Exception:
        pass

_dlog(f"=== APP START === query_params={dict(st.query_params)}")

# ── File-based logout safety net ──
LOGOUT_FLAG = PROJECT_DIR / "config" / ".logout_flag"
if LOGOUT_FLAG.exists():
    _dlog(f"SAFETY NET: flag file found, clearing auth")
    LOGOUT_FLAG.unlink()
    st.session_state.pop("authenticated", None)
    st.session_state.pop("user", None)
    st.session_state.pop("active_tab", None)
    _dlog(f"  after safety net, auth={st.session_state.get('authenticated', 'MISSING')}")

if "authenticated" not in st.session_state:
    # Try session persistence file (survives full-page navigation from tab <a href> links)
    SESSION_FILE = PROJECT_DIR / "config" / ".session_active"
    if SESSION_FILE.exists():
        # Distinguish logout (partial key clear) from tab switch (full session loss).
        # The old logout button only pops 3 keys; tab <a href> nav creates a brand-new
        # session where NO app keys exist. Check for surviving keys to detect logout.
        _survivor_keys = {"pipeline_init", "kb_stats", "config", "scraped_data",
                          "agent_messages", "annotation_result", "correction_result"}
        _is_logout = bool(_survivor_keys & set(st.session_state.keys()))
        if _is_logout:
            _dlog("logout detected via surviving session keys, deleting session file")
            SESSION_FILE.unlink()
        else:
            try:
                import json as _json
                _sdata = _json.loads(SESSION_FILE.read_text(encoding="utf-8"))
                _age = time.time() - _sdata.get("timestamp", 0)
                if _age < 86400:  # 24-hour validity
                    _dlog(f"auth restored from session file (age={_age:.0f}s)")
                    st.session_state.authenticated = True
                    st.session_state.user = {
                        "username": _sdata["username"],
                        "role": _sdata["role"],
                        "display_name": _sdata.get("display_name", _sdata["username"]),
                    }
                    from engine.auth import get_allowed_tabs
                    st.session_state.active_tab = get_allowed_tabs(_sdata["role"])[0]
                else:
                    _dlog("session file expired, clearing")
                    SESSION_FILE.unlink()
            except Exception:
                _dlog("session file corrupt, clearing")
                try:
                    SESSION_FILE.unlink()
                except Exception:
                    pass
    if "authenticated" not in st.session_state:
        _dlog(f"auth not in session, setting False")
        st.session_state.authenticated = False

_dlog(f"AUTH GATE: authenticated={st.session_state.get('authenticated', 'MISSING')}")

if not st.session_state.authenticated:
    _dlog("AUTH GATE: not authenticated, showing login page")
    from ui.login import render_login_page
    render_login_page()
    st.stop()

# ── Ensure session persistence file exists for tab <a href> navigation ──
SESSION_FILE = PROJECT_DIR / "config" / ".session_active"
if not SESSION_FILE.exists():
    _user = st.session_state.get("user", {})
    if _user:
        import json as _json2
        _sdata = _json2.dumps({
            "username": _user.get("username", ""),
            "role": _user.get("role", ""),
            "display_name": _user.get("display_name", _user.get("username", "")),
            "timestamp": time.time(),
        }, ensure_ascii=False)
        SESSION_FILE.write_text(_sdata, encoding="utf-8")
        _dlog("session file created from auth gate pass")

# Inject topbar CSS separately to ensure reliability
st.markdown("""
<style>
.topbar {
    height: 56px;
    background: linear-gradient(135deg, #0D47A1 0%, #1565C0 100%);
    display: flex;
    align-items: center;
    padding: 0 32px;
    margin: -1.2rem -2rem 1.2rem -2rem;
    box-shadow: 0 2px 8px rgba(13,71,161,0.25);
    gap: 0;
}
.topbar-logo {
    color: #fff;
    font-size: 18px;
    font-weight: 700;
    white-space: nowrap;
    margin-right: 32px;
}
.topbar-logo span { color: #00ACC1; }
.topbar-tabs {
    display: flex;
    align-items: center;
    height: 56px;
}
.topbar-tab {
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
}
.topbar-tab:hover {
    color: rgba(255,255,255,0.9) !important;
}
.topbar-tab.active {
    color: #fff !important;
}
.topbar-tab.active::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 12px;
    right: 12px;
    height: 3px;
    background: #00ACC1;
    border-radius: 3px 3px 0 0;
}
.topbar-user {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 12px;
    color: rgba(255,255,255,0.8);
    font-size: 13px;
}
.topbar-avatar {
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
}
/* Override any leaked blue gradient from old theme.css rules.
   The .topbar class is a plain DIV (not stHorizontalBlock), so this
   reset does not affect the topbar itself. */
div[data-testid="stHorizontalBlock"] {
    background: none !important;
}
</style>
""", unsafe_allow_html=True)

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

# Resolve active tab from query param or deferred switch BEFORE rendering topbar.
try:
    _tid = int(st.query_params.get('tab', '0'))
except (ValueError, TypeError):
    _tid = 0
_rtab = TAB_LABELS[_tid] if 0 <= _tid < len(TAB_LABELS) else TAB_LABELS[0]
if "active_tab" not in st.session_state:
    st.session_state.active_tab = _rtab
elif _rtab != st.session_state.active_tab and _rtab in TAB_LABELS:
    st.session_state.active_tab = _rtab

# Handle deferred tab switches (e.g. from citation button "查看 case")
if st.session_state.get("_pending_tab"):
    pending = st.session_state.pop("_pending_tab")
    _tab_map = {"扫地僧": "知识库"}  # old → new name mapping
    st.session_state.active_tab = _tab_map.get(pending, pending)
    # Sync query param so URL matches active tab on subsequent reruns
    _new_idx = TAB_LABELS.index(st.session_state.active_tab)
    st.query_params['tab'] = str(_new_idx)

if st.session_state.active_tab not in TAB_LABELS:
    st.session_state.active_tab = TAB_LABELS[0]
active_tab = st.session_state.active_tab

# Topbar with integrated tabs — rendered as pure HTML with anchor links
# for reliable blue-gradient styling (Streamlit st.columns + CSS selectors
# cannot reliably target a specific horizontal block due to DOM wrapping).
_tabs_html = ""
for _i, _label in enumerate(TAB_LABELS):
    _is_active = " active" if _label == active_tab else ""
    _tabs_html += f'<a class="topbar-tab{_is_active}" href="?tab={_i}">{_label}</a>'

st.html(
    f'<div class="topbar">'
    f'<div class="topbar-logo">舆情智能标注 <span>|</span> OPS</div>'
    f'<nav class="topbar-tabs">{_tabs_html}</nav>'
    f'<div class="topbar-user"><span>{st.session_state.get("user", {}).get("display_name", "管理员")}</span><div class="topbar-avatar">{st.session_state.get("user", {}).get("display_name", "管")[0]}</div></div>'
    f'</div>'
)

active_tab = st.session_state.active_tab
curr_idx = TAB_LABELS.index(active_tab) if active_tab in TAB_LABELS else 0
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
        st.markdown('<p class="section-title">📊 总览仪表板</p>', unsafe_allow_html=True)
        st.info('系统尚未积累足够数据。请先运行 Monitor 巡检或录入案例。')
        qs1, qs2 = st.columns(2)
        with qs1:
            if st.button('📡 执行 Monitor 巡检', use_container_width=True, key='ov_empty_monitor'):
                st.session_state._pending_tab = 'Monitor'
        with qs2:
            if st.button('📝 录入新案例', use_container_width=True, key='ov_empty_entry'):
                st.session_state._pending_tab = '录入研判'
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
        from datetime import datetime as _dt
        st.markdown(
            '<div class="page-header">'
            '<div>'
            '<h1>总览仪表板</h1>'
            f'<div class="subtitle">舆情数据实时监控 · 更新于 {_dt.now().strftime("%Y-%m-%d %H:%M")}</div>'
            '</div>'
            '<div class="date-badge"><span>📅</span><span>最近7天</span></div>'
            '</div>',
            unsafe_allow_html=True
        )

        # Metric cards (4 in a row)
        st.markdown(
            '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;">'
            f'<div class="metric-card highlight"><div class="label">📋 总案例数</div><div class="value">{total}</div><div class="change up">↑ 12.5% 较上周</div></div>'
            f'<div class="metric-card warn"><div class="label">⚠️ 高优待处理</div><div class="value">{p0p1}</div><div class="change down">↑ {p0p1} 较昨日</div></div>'
            f'<div class="metric-card"><div class="label">📡 覆盖平台</div><div class="value">{len(plat)}</div><div class="change up">小红书 · 抖音 · 微博 · B站</div></div>'
            f'<div class="metric-card accent"><div class="label">📌 待跟进案例</div><div class="value">{pending}</div><div class="change down">↓ 5 较昨日</div></div>'
            '</div>',
            unsafe_allow_html=True
        )

        # Two-column: severity + quick actions
        lcol, rcol = st.columns(2, gap="small")
        with lcol:
            sev_total = sum(sev.values()) or 1
            sev_labels = {'P0': 'P0 严重', 'P1': 'P1 高危', 'P2': 'P2 中危', 'P3': 'P3 低危'}
            segs = []
            for level, cls in [('P0', 'p0'), ('P1', 'p1'), ('P2', 'p2'), ('P3', 'p3')]:
                cnt = sev.get(level, 0)
                if cnt:
                    pct = round(cnt / sev_total * 100)
                    segs.append(f'<div class="seg {cls}" style="flex:{max(pct,8)}">{level} {pct}%</div>')
            legend = []
            for level, cls in [('P0', 'p0'), ('P1', 'p1'), ('P2', 'p2'), ('P3', 'p3')]:
                cnt = sev.get(level, 0)
                if cnt:
                    legend.append(f'<div class="item"><span class="dot {cls}"></span>{sev_labels[level]} · {cnt} 条</div>')
            # Single st.markdown — all children are HTML, no Streamlit widgets in between
            sev_html = '<div class="card"><div class="card-title">⚠️ 严重度分布</div>'
            if segs:
                sev_html += f'<div class="severity-bar">{"".join(segs)}</div>'
            if legend:
                sev_html += f'<div class="severity-legend">{"".join(legend)}</div>'
            sev_html += '</div>'
            st.markdown(sev_html, unsafe_allow_html=True)

        with rcol:
            # Card open/close split across st.markdown() calls — required because
            # Streamlit st.button() widgets render as siblings, not children of HTML.
            st.markdown(
                '<div class="card">'
                '<div class="card-title">⚡ 快捷操作</div>',
                unsafe_allow_html=True
            )
            qa1, qa2 = st.columns(2)
            with qa1:
                if st.button("🔍 Monitor 巡检\n启动新一轮巡检", key="qa_monitor", use_container_width=True):
                    st.session_state._pending_tab = "Monitor"
            with qa2:
                if st.button("📝 录入新案例\n手动录入舆情案例", key="qa_entry", use_container_width=True):
                    st.session_state._pending_tab = "录入研判"
            qa3, qa4 = st.columns(2)
            with qa3:
                if st.button(f"⚡ 案例处置\n待处理 {pending} 条", key="qa_disposition", use_container_width=True):
                    st.session_state._pending_tab = "案例处置"
            with qa4:
                if st.button(f"🏴 高危追踪\n高优跟进 {p0p1} 条", key="qa_tracking", use_container_width=True):
                    st.session_state._pending_tab = "高危追踪"
            st.markdown('</div>', unsafe_allow_html=True)

        # Platform distribution
        if plat:
            plat_colors = {
                '小红书': {'bg': '#ff2442', 'abbr': '红'},
                '抖音': {'bg': '#1e1e1e', 'abbr': '抖'},
                'YouTube': {'bg': '#ff0000', 'abbr': 'YT'},
                '微博': {'bg': '#e6162d', 'abbr': '微'},
                'B站': {'bg': '#fb7299', 'abbr': 'B'},
                '公众号': {'bg': '#07c160', 'abbr': '公'},
            }
            items_html = ''
            for pf, cnt in sorted(plat.items(), key=lambda x: -x[1]):
                info = plat_colors.get(pf, {'bg': '#64748B', 'abbr': pf[:2]})
                pct = int(cnt / max_cnt * 100) if max_cnt else 0
                items_html += (
                    f'<div class="platform-item">'
                    f'<div class="pf-icon" style="background:{info["bg"]};">{html.escape(info["abbr"])}</div>'
                    f'<div class="pf-info">'
                    f'<div class="pf-name">{html.escape(pf)}</div>'
                    f'<div class="pf-count">{cnt} 条</div>'
                    f'<div class="pf-bar-wrap"><div class="pf-bar-fill" style="width:{pct}%;background:{info["bg"]};"></div></div>'
                    f'</div></div>'
                )
            st.markdown(
                '<div class="card">'
                '<div class="card-title">🌐 平台分布</div>'
                '<div class="platform-grid">' + items_html + '</div>'
                '</div>',
                unsafe_allow_html=True
            )

    with side_col:
        st.markdown(
            f'<div class="sidebar-card">'
            f'<h3>⏰ 待处理任务 <span class="badge orange">{pending}</span></h3>'
            f'<ul class="sidebar-list">'
            f'<li><span>待标注案例</span><span class="val">{total} 条</span></li>'
            f'<li><span>待审核结果</span><span class="val">0 条</span></li>'
            f'<li><span>待跟进处置</span><span class="val">{pending} 条</span></li>'
            f'</ul></div>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="sidebar-card">'
            f'<h3>📊 今日动态</h3>'
            f'<p style="font-size:12px;color:#64748B;">暂无新动态</p>'
            f'</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<div class="sidebar-card">'
            '<h3>🔄 系统状态</h3>'
            '<ul class="sidebar-list">'
            '<li><span>巡检服务</span><span style="color:#16a34a;font-weight:500;">● 运行中</span></li>'
            '<li><span>标注队列</span><span style="color:#f59e0b;font-weight:500;">● 拥堵 3</span></li>'
            '<li><span>数据网关</span><span style="color:#16a34a;font-weight:500;">● 正常</span></li>'
            '</ul></div>',
            unsafe_allow_html=True
        )
# Tab routing — match by label string, not index (TAB_LABELS varies by role)
# ═══════════════════════════════════════════════════════════════════════════════

if active_tab == "总览":
    _render_overview()
elif active_tab == "Monitor":
    render_tab3()
elif active_tab == "录入研判":
    render_tab_entry()
elif active_tab == "案例处置":
    render_tab4()
elif active_tab == "知识库":
    render_tab_knowledge()
elif active_tab == "报告":
    render_tab6()
elif active_tab == "高危追踪":
    render_tab_tracking()
elif active_tab == "设置":
    import ui.tab_settings as _ts
    from importlib import reload as _reload
    _reload(_ts)
    _ts.render_tab_settings()

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

