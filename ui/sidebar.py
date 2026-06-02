# -*- coding: utf-8 -*-
"""Sidebar rendering for the annotation dashboard.

Extracted from app.py — no logic changes, pure code movement.
"""

import json as _json
from datetime import datetime as _dt

import streamlit as st

from engine.annotate import (
    build_system_prompt,
    load_config,
)
from ui.shared import ENGINE_DIR, PROJECT_DIR
from ui.theme import spacer


def render_sidebar(_patrol_pending: bool):
    """Render the sidebar with system status, dashboard, patrol, and XHS login."""

    with st.sidebar:
        # ── User info & logout ──────────────────────────────────────
        from ui.login import render_logout_button
        render_logout_button()
        st.markdown("<hr>", unsafe_allow_html=True)

        # Auto-load KB on first visit
        if st.session_state.config is None:
            config = load_config()
            _, kb_stats = build_system_prompt()
            st.session_state.config = config
            st.session_state.system_prompt_loaded = True
            st.session_state.kb_stats = kb_stats

        # ── Section: System ─────────────────────────────────────────
        with st.expander("⚙️ 系统", expanded=False):
            if st.button("🔄 刷新知识库", use_container_width=True):
                with st.spinner("加载中..."):
                    config = load_config()
                    _, kb_stats = build_system_prompt()
                    st.session_state.config = config
                    st.session_state.system_prompt_loaded = True
                    st.session_state.kb_stats = kb_stats

            kb = st.session_state.kb_stats
            if kb:
                loaded = sum(1 for v in kb["layers"].values() if v["status"] == "loaded")
                st.caption(f"知识库: {loaded}/{len(kb['layers'])} 页")
                st.caption(f"模型: {st.session_state.config.get('model', '?')}")
            api_key = (st.session_state.config or {}).get("api_key", "")
            st.caption(f"API Key: {'✅' if api_key else '⚠️ 未配置'}")

        # ── Section: Dashboard ──────────────────────────────────────
        with st.expander("📊 概览", expanded=False):
            try:
                from agents.curator import query_stats
                stats = query_stats()
                total = stats["total_cases"]
                sev_count = stats["severity_dist"]
                plat_count = stats["platform_dist"]
                c1, c2, c3 = st.columns(3)
                c1.metric("案例", total)
                c2.metric("P0/P1", sev_count.get("P0", 0) + sev_count.get("P1", 0))
                c3.metric("平台", len(plat_count))
                st.caption(
                    f"P0:{sev_count['P0']} P1:{sev_count['P1']} "
                    f"P2:{sev_count['P2']} P3:{sev_count['P3']}"
                )
            except Exception:
                st.caption("仪表盘加载失败")

        # ── Section: Auto duty ──────────────────────────────────────
        st.markdown("<hr>", unsafe_allow_html=True)
        st.caption("🛡️ 自动值守")

        from scheduler import (
            load_scheduler_config,
            save_scheduler_config,
            get_scheduler_status as _get_sched_status,
        )

        sched_cfg = load_scheduler_config()
        sched_stat = _get_sched_status()
        is_auto = sched_cfg.get("auto_mode", False)
        is_sched_running = sched_stat.get("running", False)

        # Start / Stop buttons
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button(
                "▶️ 启动值守" if not is_auto else "🟢 值守中",
                use_container_width=True,
                disabled=is_auto,
                key="auto_start_btn",
            ):
                sched_cfg["auto_mode"] = True
                save_scheduler_config(sched_cfg)
                st.success("值守已启动，调度器将在下一轮检查中注册定时作业")
                import time as _time
                _time.sleep(1)
                st.rerun()
        with bc2:
            if st.button(
                "⏹️ 停止值守",
                use_container_width=True,
                disabled=not is_auto,
                key="auto_stop_btn",
            ):
                sched_cfg["auto_mode"] = False
                save_scheduler_config(sched_cfg)
                st.warning("值守已停止")
                import time as _time
                _time.sleep(1)
                st.rerun()

        # Status indicator
        if is_auto and is_sched_running:
            st.caption("● 值守运行中 — 定时作业已注册")
        elif is_auto and not is_sched_running:
            st.caption("○ 值守已启用，等待调度器线程启动...")
        else:
            st.caption("○ 值守已停止")

        # Daily report time
        new_daily_time = st.text_input(
            "日报时间",
            value=sched_cfg.get("daily_report_time", "21:07"),
            max_chars=5,
            key="sched_daily_time",
            help="格式: HH:MM (如 21:07)",
        )

        freq_options = ["每2小时", "每4小时", "每6小时", "每8小时"]
        freq_map = {"每2小时": "2h", "每4小时": "4h", "每6小时": "6h", "每8小时": "8h"}
        rev_freq = {v: k for k, v in freq_map.items()}
        cur_freq = sched_cfg.get("pipeline_frequency", "daily")
        cur_freq_idx = list(freq_map.values()).index(cur_freq) if cur_freq in freq_map else 0

        new_frequency = st.selectbox(
            "自动抓取频次",
            freq_options,
            index=cur_freq_idx,
            key="sched_frequency",
        )

        if st.button("💾 保存设置", use_container_width=True, key="sched_save_btn"):
            new_cfg = dict(sched_cfg)
            new_cfg["daily_report_time"] = new_daily_time
            new_cfg["pipeline_frequency"] = freq_map[new_frequency]
            save_scheduler_config(new_cfg)
            st.success("设置已保存，调度器将在 60 秒内自动应用")
            import time as _time
            _time.sleep(0.5)
            st.rerun()

        # ── Section: Pipeline ─────────────────────────────────────────
        st.markdown("<hr>", unsafe_allow_html=True)
        pipeline_expanded = True  # always show pipeline section

        with st.expander("🔁 自动化流水线", expanded=True):
            from pipeline import get_pipeline_status, trigger_pipeline, reset_pipeline

            pstat = get_pipeline_status()
            is_running = pstat.get("is_running", False)

            for step in pstat.get("steps", []):
                s = step["status"]
                icons = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}
                icon = icons.get(s, "⏳")
                cols = st.columns([1, 3])
                if s == "running":
                    cols[0].caption(f"{icon} {step['label']}")
                    cols[1].progress(step.get("progress", 0))
                    if step.get("details"):
                        st.caption(f"  {step['details']}")
                elif s == "done":
                    cols[0].caption(f"{icon} {step['label']}")
                    cols[1].caption(step.get("details", "")[:40])
                elif s == "error":
                    st.caption(f"{icon} {step['label']}: {step.get('error', '')[:50]}")
                else:
                    cols[0].caption(f"{icon} {step['label']}")
                    cols[1].caption("")

            c1, c2 = st.columns(2)
            with c1:
                init_status = st.selectbox(
                    "初始状态",
                    ["待跟进", "处理中"],
                    index=0,
                    key="pipeline_init_status",
                    help="流水线生成的新案例初始状态",
                )
            with c2:
                sort_preference = st.selectbox(
                    "排序方式",
                    ["默认排序", "时间排序"],
                    index=0,
                    key="pipeline_sort_pref",
                    help="搜索结果的排序方式：默认(相关性/热度) 或 按发布时间",
                )

            c3, c4 = st.columns(2)
            with c3:
                if st.button("▶️ 执行流水线", use_container_width=True,
                             disabled=is_running, key="pipeline_run_btn"):
                    sort_val = "date" if sort_preference == "时间排序" else "default"
                    trigger_pipeline(source="manual", init_status=init_status,
                                     sort_preference=sort_val)
                    st.rerun()
            with c4:
                if st.button("🔄 重置", use_container_width=True,
                             disabled=is_running, key="pipeline_reset_btn"):
                    reset_pipeline()
                    st.rerun()

            if pstat.get("errors"):
                with st.expander("⚠️ 错误日志", expanded=False):
                    for e in pstat["errors"][-5:]:
                        st.caption(f"- {e[:100]}")

            # Auto-rerun while pipeline is running; one final refresh after completion
            if is_running:
                st.session_state._pipeline_was_running = True
                import time as _time
                _time.sleep(1.5)
                st.rerun()
            elif st.session_state.pop("_pipeline_was_running", False):
                st.rerun()

        # ── Section: Patrol & tools ───────────────────────────────────
        st.markdown("<hr>", unsafe_allow_html=True)
        with st.expander("📡 巡检 & 登录", expanded=bool(_patrol_pending)):
            patrol_urls_file = ENGINE_DIR / "monitored_urls.json"
            if patrol_urls_file.exists():
                patrol_urls = _json.loads(patrol_urls_file.read_text(encoding="utf-8"))
                st.caption(f"监控 {len(patrol_urls)} 个链接")
                if st.button("立即巡检", use_container_width=True, key="patrol_btn"):
                    st.session_state._patrol_pending = True
                    st.rerun()
                # Execute patrol if pending (routed through Orchestrator per PRD §3.5)
                if _patrol_pending:
                    results = []
                    p0p1 = 0
                    status = st.empty()
                    from agents.orchestrator import run_passive_analysis
                    for u in patrol_urls:
                        status.info(f"巡检中: {u[:60]}...")
                        try:
                            pr = run_passive_analysis(u, "侧边栏巡检")
                            if pr.success and pr.annotation:
                                sev = pr.annotation.severity
                                if sev in ("P0", "P1"):
                                    p0p1 += 1
                                results.append({
                                    "url": u, "severity": sev,
                                    "action": pr.annotation.triage,
                                    "summary": pr.annotation.summary[:60],
                                })
                        except Exception:
                            pass
                    status.empty()
                    st.session_state._patrol_result = {"ok": len(results), "total": len(patrol_urls), "p0p1": p0p1, "items": results}
                    st.session_state._needs_rerun = True
                # Show last patrol result
                if st.session_state.get("_patrol_result"):
                    pr = st.session_state._patrol_result
                    ok = pr["ok"]; total = pr["total"]; p0p1 = pr["p0p1"]
                    st.caption(f"上次巡检: {ok}/{total} 成功, P0/P1: {p0p1}")
                    if p0p1 > 0:
                        st.error(f"⚠️ {p0p1} 条高优案例需关注")
                        for item in pr.get("items", []):
                            if item.get("severity") in ("P0", "P1"):
                                st.markdown(f"- **{item['severity']}** {item['summary'][:50]}...")
            else:
                st.caption("无监控配置")

            st.markdown("<hr>", unsafe_allow_html=True)
            st.caption("小红书登录状态")
            try:
                cookie_file = ENGINE_DIR / ".xhs_cookies.json"
                if cookie_file.exists():
                    with open(cookie_file, "r", encoding="utf-8") as _f:
                        cookie_data = _json.load(_f)
                    saved_ts = cookie_data.get("saved_at", 0)
                    if saved_ts:
                        saved_dt = _dt.fromtimestamp(saved_ts)
                        days_left = 7 - (_dt.now() - saved_dt).days
                        if days_left <= 0:
                            st.error("Cookie 已过期")
                        elif days_left <= 1:
                            st.warning(f"Cookie 即将过期 ({days_left}天)")
                        else:
                            st.caption(f"Cookie 有效 (剩余 {days_left} 天)")
            except Exception:
                pass
            if st.button("刷新小红书登录", use_container_width=True, key="sidebar_xhs_login"):
                from engine.xhs_fetcher import bootstrap_cookies
                with st.spinner("正在打开浏览器..."):
                    if bootstrap_cookies(force=True):
                        st.success("登录成功！")
                    else:
                        st.error("登录失败")

            st.markdown("<hr>", unsafe_allow_html=True)
            st.caption("抖音登录状态")
            try:
                tt_cookie_file = ENGINE_DIR / ".tt_cookies.json"
                tt_valid = False
                if tt_cookie_file.exists():
                    with open(tt_cookie_file, "r", encoding="utf-8") as _f:
                        tt_data = _json.load(_f)
                    saved_ts = tt_data.get("saved_at", 0)
                    if saved_ts:
                        saved_dt = _dt.fromtimestamp(saved_ts)
                        days_left = 7 - (_dt.now() - saved_dt).days
                        if days_left <= 0:
                            st.error("Cookie 已过期")
                        elif days_left <= 1:
                            st.warning(f"Cookie 即将过期 ({days_left}天)")
                        else:
                            tt_valid = True
                            st.caption(f"Cookie 有效 (剩余 {days_left} 天)")
                # Also check TikTokDownloader settings.json
                if not tt_valid:
                    try:
                        from engine.tt_fetcher import _check_cookie_valid
                        if _check_cookie_valid():
                            st.caption("Cookie 有效 (TikTokDownloader)")
                            tt_valid = True
                    except Exception:
                        pass
                if not tt_valid and not tt_cookie_file.exists():
                    st.caption("未登录")
            except Exception:
                st.caption("未登录")
            if st.button("刷新抖音登录", use_container_width=True, key="sidebar_dy_login"):
                from engine.tt_fetcher import bootstrap_douyin_cookies
                with st.spinner("正在打开浏览器..."):
                    if bootstrap_douyin_cookies(force=True):
                        st.success("登录成功！")
                    else:
                        st.error("登录失败")

            st.markdown("<hr>", unsafe_allow_html=True)
            st.caption("微信公众号 (搜狗微信搜索)")
            st.caption("公开搜索，无需登录")
