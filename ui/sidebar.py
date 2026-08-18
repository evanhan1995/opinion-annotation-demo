# -*- coding: utf-8 -*-
"""Sidebar rendering for the annotation dashboard — Figma page 6 design."""

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
    """Render the sidebar with Figma-styled sections."""

    with st.sidebar:
        # Auto-load KB on first visit
        if st.session_state.config is None:
            config = load_config()
            _, kb_stats = build_system_prompt()
            st.session_state.config = config
            st.session_state.system_prompt_loaded = True
            st.session_state.kb_stats = kb_stats

        # ── Sidebar Header (Figma blue gradient) ────────────────────
        st.markdown(
            '<div class="sidebar-header">'
            '<h2>⚙️ 系统控制台</h2>'
            '<div class="sub">舆情智能标注系统 v2.4.1</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

        # ── User info + Logout ────────────────────────────────────────
        user = st.session_state.get("user", {})
        if user.get("display_name"):
            from engine.auth import get_role_label
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #f0f2f5;margin-bottom:8px;">'
                f'<div style="width:36px;height:36px;border-radius:50%;background:#00ACC1;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:600;font-size:16px;">{user["display_name"][0]}</div>'
                f'<div><div style="font-size:13px;font-weight:500;">{user["display_name"]}</div><div style="font-size:11px;color:#64748B;">{get_role_label(user.get("role", ""))}</div></div>'
                f'</div>', unsafe_allow_html=True)
            # Inline logout: avoids stale login.py cache issue
            if st.button("退出登录", use_container_width=True, key="logout_btn"):
                import base64
                REMEMBERED_PATH = PROJECT_DIR / "config" / "remembered_user.json"
                SESSION_PATH = PROJECT_DIR / "config" / ".session_active"
                if REMEMBERED_PATH.exists():
                    REMEMBERED_PATH.unlink()
                if SESSION_PATH.exists():
                    SESSION_PATH.unlink()
                for _k in ("authenticated", "user", "active_tab"):
                    st.session_state.pop(_k, None)
                st.rerun()
            st.markdown("<hr>", unsafe_allow_html=True)

        # ── Section: System Status ───────────────────────────────────
        st.markdown('<div class="section-title">系统区</div>', unsafe_allow_html=True)

        # System status indicators
        kb = st.session_state.kb_stats
        kb_loaded = sum(1 for v in kb["layers"].values() if v["status"] == "loaded") if kb else 0
        api_key = (st.session_state.config or {}).get("api_key", "")

        status_items = [
            ("green", "系统状态", "正常 · 运行中"),
        ]
        if api_key:
            status_items.append(("green", "API Key", "已配置"))
        else:
            status_items.append(("red", "API Key", "⚠️ 未配置"))
        status_items.append(("green" if kb_loaded else "yellow", "知识库", f"{kb_loaded} 页已加载" if kb_loaded else "加载中..."))

        sys_html = ""
        for dot_color, label, value in status_items:
            sys_html += (
                f'<div class="sys-status">'
                f'<span class="dot {dot_color}"></span>'
                f'<span class="label">{label}</span>'
                f'<span class="value">{value}</span>'
                f'</div>'
            )
        st.markdown(sys_html, unsafe_allow_html=True)

        # KB refresh button
        if st.button("🔄 刷新知识库", use_container_width=True, key="sidebar_refresh_kb"):
            with st.spinner("加载中..."):
                config = load_config()
                _, kb_stats = build_system_prompt()
                st.session_state.config = config
                st.session_state.system_prompt_loaded = True
                st.session_state.kb_stats = kb_stats
                st.rerun()

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

        # ── Section: Overview ────────────────────────────────────────
        st.markdown('<div class="section-title">概览</div>', unsafe_allow_html=True)

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
                f"P0:{sev_count.get('P0',0)} P1:{sev_count.get('P1',0)} "
                f"P2:{sev_count.get('P2',0)} P3:{sev_count.get('P3',0)}"
            )
        except Exception:
            st.caption("仪表盘加载中...")

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

        # ── Section: Auto Control ────────────────────────────────────
        st.markdown('<div class="section-title">自动值守控制</div>', unsafe_allow_html=True)

        from scheduler import (
            load_scheduler_config,
            save_scheduler_config,
            get_scheduler_status as _get_sched_status,
        )

        sched_cfg = load_scheduler_config()
        sched_stat = _get_sched_status()
        is_auto = sched_cfg.get("auto_mode", False)
        is_sched_running = sched_stat.get("running", False)

        # Toggle-style controls using buttons
        auto_html = '<div class="auto-control">'

        # Auto patrol toggle
        auto_html += (
            f'<div class="control-row">'
            f'<div class="control-label">自动巡检<span class="sub">每 30 分钟执行一轮</span></div>'
            f'<span style="font-size:12px;font-weight:500;color:{"#16a34a" if is_auto else "#94a3b8"};">'
            f'{"● 运行中" if is_auto else "○ 已停止"}</span>'
            f'</div>'
        )

        # Pipeline frequency
        freq_display = sched_cfg.get("pipeline_frequency", "daily")
        freq_text = {"daily": "每日", "2h": "每2小时", "4h": "每4小时", "6h": "每6小时", "8h": "每8小时"}.get(freq_display, "每日")
        auto_html += (
            f'<div class="control-row">'
            f'<div class="control-label">流水线频次<span class="sub">当前: {freq_text}</span></div>'
            f'</div>'
        )

        auto_html += '</div>'
        st.markdown(auto_html, unsafe_allow_html=True)

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
                st.success("值守已启动")
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
            st.markdown('<span class="status-dot active"></span> 值守运行中 — 定时作业已注册', unsafe_allow_html=True)
        elif is_auto and not is_sched_running:
            st.markdown('<span class="status-dot inactive"></span> 值守已启用，等待调度器线程启动...', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-dot inactive"></span> 值守已停止', unsafe_allow_html=True)

        # Schedule settings
        new_daily_time = st.text_input(
            "日报时间",
            value=sched_cfg.get("daily_report_time", "21:07"),
            max_chars=5,
            key="sched_daily_time",
            help="格式: HH:MM",
        )
        freq_options = ["每2小时", "每4小时", "每6小时", "每8小时"]
        freq_map = {"每2小时": "2h", "每4小时": "4h", "每6小时": "6h", "每8小时": "8h"}
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

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

        # ── Section: Pipeline Progress ───────────────────────────────
        st.markdown('<div class="section-title">流水线进度</div>', unsafe_allow_html=True)

        from pipeline import get_pipeline_status, trigger_pipeline, reset_pipeline

        pstat = get_pipeline_status()
        is_running = pstat.get("is_running", False)

        # Render pipeline steps with Figma styling
        pipe_html = '<div class="pipeline">'
        for step in pstat.get("steps", []):
            s = step["status"]
            if s == "done":
                icon_cls = "done"
                icon_text = "✓"
                status_text = "已完成"
            elif s == "running":
                icon_cls = "progress"
                icon_text = str(pstat.get("steps", []).index(step) + 1)
                status_text = f"进行中 {int(step.get('progress', 0) * 100)}%"
            elif s == "error":
                icon_cls = "pending"
                icon_text = "✗"
                status_text = "错误"
            else:
                icon_cls = "pending"
                icon_text = str(pstat.get("steps", []).index(step) + 1)
                status_text = "等待中"

            pipe_html += (
                f'<div class="pipeline-step">'
                f'<div class="step-icon {icon_cls}">{icon_text}</div>'
                f'<div class="step-info"><div class="step-name">{step["label"]}</div>'
                f'<div class="step-status">{status_text}</div></div>'
                f'<div class="step-time">{step.get("details", "")[:20] or "-"}</div>'
                f'</div>'
            )
        pipe_html += '</div>'
        st.markdown(pipe_html, unsafe_allow_html=True)

        # Pipeline controls
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
                help="搜索结果的排序方式",
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

        # Auto-rerun while pipeline is running
        if is_running:
            st.session_state._pipeline_was_running = True
            import time as _time
            _time.sleep(1.5)
            st.rerun()
        elif st.session_state.pop("_pipeline_was_running", False):
            st.rerun()

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

        # ── Section: Login Status ────────────────────────────────────
        st.markdown('<div class="section-title">巡检登录状态</div>', unsafe_allow_html=True)

        login_html = ""

        # Weibo
        login_html += (
            '<div class="login-item">'
            '<span class="login-dot active"></span>'
            '<span class="pname">微博</span>'
            '<span class="pstatus">公开搜索</span>'
            '</div>'
        )

        # Xiaohongshu
        xhs_status = "未登录"
        xhs_dot = "idle"
        try:
            cookie_file = ENGINE_DIR / ".xhs_cookies.json"
            if cookie_file.exists():
                with open(cookie_file, "r", encoding="utf-8") as _f:
                    cookie_data = _json.load(_f)
                saved_ts = cookie_data.get("saved_at", 0)
                if saved_ts:
                    days_left = 7 - (_dt.now() - _dt.fromtimestamp(saved_ts)).days
                    if days_left <= 0:
                        xhs_status = "已过期"
                        xhs_dot = "error"
                    elif days_left <= 1:
                        xhs_status = f"即将过期 ({days_left}天)"
                        xhs_dot = "active"
                    else:
                        xhs_status = f"Cookie 有效 ({days_left}天)"
                        xhs_dot = "active"
        except Exception:
            pass
        login_html += (
            f'<div class="login-item">'
            f'<span class="login-dot {xhs_dot}"></span>'
            f'<span class="pname">小红书</span>'
            f'<span class="pstatus">{xhs_status}</span>'
            f'</div>'
        )

        # Douyin
        dy_status = "未登录"
        dy_dot = "idle"
        try:
            tt_cookie_file = ENGINE_DIR / ".tt_cookies.json"
            if tt_cookie_file.exists():
                with open(tt_cookie_file, "r", encoding="utf-8") as _f:
                    tt_data = _json.load(_f)
                saved_ts = tt_data.get("saved_at", 0)
                if saved_ts:
                    days_left = 7 - (_dt.now() - _dt.fromtimestamp(saved_ts)).days
                    if days_left <= 0:
                        dy_status = "已过期"
                        dy_dot = "error"
                    elif days_left <= 1:
                        dy_status = f"即将过期 ({days_left}天)"
                        dy_dot = "active"
                    else:
                        dy_status = f"Cookie 有效 ({days_left}天)"
                        dy_dot = "active"
            if dy_dot == "idle":
                try:
                    from engine.tt_fetcher import _check_cookie_valid
                    if _check_cookie_valid():
                        dy_status = "Cookie 有效"
                        dy_dot = "active"
                except Exception:
                    pass
        except Exception:
            pass
        login_html += (
            f'<div class="login-item">'
            f'<span class="login-dot {dy_dot}"></span>'
            f'<span class="pname">抖音</span>'
            f'<span class="pstatus">{dy_status}</span>'
            f'</div>'
        )

        # B站
        login_html += (
            '<div class="login-item">'
            '<span class="login-dot idle"></span>'
            '<span class="pname">B站</span>'
            '<span class="pstatus">公开搜索</span>'
            '</div>'
        )

        # YouTube
        login_html += (
            '<div class="login-item">'
            '<span class="login-dot idle"></span>'
            '<span class="pname">YouTube</span>'
            '<span class="pstatus">免登录</span>'
            '</div>'
        )

        # WeChat
        login_html += (
            '<div class="login-item">'
            '<span class="login-dot active"></span>'
            '<span class="pname">公众号</span>'
            '<span class="pstatus">公开搜索</span>'
            '</div>'
        )

        st.markdown(login_html, unsafe_allow_html=True)

        # Login buttons
        lc1, lc2 = st.columns(2)
        with lc1:
            if st.button("🔄 小红书登录", use_container_width=True, key="sidebar_xhs_login"):
                from engine.xhs_fetcher import bootstrap_cookies
                with st.spinner("正在打开浏览器..."):
                    if bootstrap_cookies(force=True):
                        st.success("登录成功！")
                    else:
                        st.error("登录失败")
        with lc2:
            if st.button("🔄 抖音登录", use_container_width=True, key="sidebar_dy_login"):
                from engine.tt_fetcher import bootstrap_douyin_cookies
                with st.spinner("正在打开浏览器..."):
                    if bootstrap_douyin_cookies(force=True):
                        st.success("登录成功！")
                    else:
                        st.error("登录失败")

        # Patrol button
        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
        patrol_urls_file = ENGINE_DIR / "monitored_urls.json"
        if patrol_urls_file.exists():
            try:
                raw = patrol_urls_file.read_text(encoding="utf-8").strip()
                patrol_urls = _json.loads(raw) if raw else []
            except _json.JSONDecodeError:
                patrol_urls = []
            if st.button(f"📡 立即巡检 ({len(patrol_urls)} 链接)", use_container_width=True, key="patrol_btn"):
                st.session_state._patrol_pending = True
                st.rerun()

            # Execute patrol if pending
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

        # ── Footer ───────────────────────────────────────────────────
        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
        st.markdown('<div style="height:1px;background:#e2e8f0;margin:8px 0;"></div>', unsafe_allow_html=True)
        now_str = _dt.now().strftime("%Y-%m-%d %H:%M")
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;padding:4px 8px;">'
            f'<span style="font-size:11px;color:#64748B;">最后活动: {now_str}</span>'
            f'<span style="font-size:11px;color:#64748B;">🔄 同步中</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
