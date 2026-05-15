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
    annotate_one_stream,
    format_user_message,
)
from engine.scraper import scrape
from ui.shared import ENGINE_DIR, PROJECT_DIR, _do_ingest


def render_sidebar(_patrol_pending: bool):
    """Render the sidebar with system status, dashboard, patrol, and XHS login."""

    with st.sidebar:
        st.subheader("⚙️ 系统")

        # Auto-load KB on first visit
        if st.session_state.config is None:
            config = load_config()
            _, kb_stats = build_system_prompt()
            st.session_state.config = config
            st.session_state.system_prompt_loaded = True
            st.session_state.kb_stats = kb_stats

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
            st.caption(f"知识库: {loaded}/{len(kb['layers'])} 页 | 模型: {st.session_state.config.get('model', '?')}")
        api_key = (st.session_state.config or {}).get("api_key", "")
        st.caption(f"API Key: {'✅' if api_key else '⚠️ 未配置'}")

        # Dashboard (always visible, compact)
        st.divider()
        try:
            cases_dir = PROJECT_DIR / "wiki" / "cases"
            case_files = sorted(cases_dir.glob("case-*.md"))
            total = len(case_files)
            sev_count = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
            plat_count = {}
            for cf in case_files:
                text = cf.read_text(encoding="utf-8")
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].split("\n"):
                        line = line.strip()
                        if line.startswith("severity:"):
                            s = line.split(":")[1].strip()
                            if s in sev_count:
                                sev_count[s] += 1
                        elif line.startswith("platform:"):
                            p = line.split(":")[1].strip()
                            if p and p != "?":
                                plat_count[p] = plat_count.get(p, 0) + 1
            c1, c2, c3 = st.columns(3)
            c1.metric("案例", total)
            c2.metric("P0/P1", sev_count.get("P0", 0) + sev_count.get("P1", 0))
            c3.metric("平台", len(plat_count))
            st.caption(f"P0:{sev_count['P0']} P1:{sev_count['P1']} P2:{sev_count['P2']} P3:{sev_count['P3']}" +
                       (f"  |  " + " ".join(f"{k}:{v}" for k, v in sorted(plat_count.items(), key=lambda x: -x[1])[:4]) if plat_count else ""))
        except Exception:
            st.caption("仪表盘加载失败")

        # 监控 & 工具
        st.divider()
        with st.expander("📡 巡检 & 登录", expanded=bool(_patrol_pending)):
            patrol_urls_file = ENGINE_DIR / "monitored_urls.json"
            if patrol_urls_file.exists():
                patrol_urls = _json.loads(patrol_urls_file.read_text(encoding="utf-8"))
                st.caption(f"监控 {len(patrol_urls)} 个链接")
                if st.button("立即巡检", use_container_width=True, key="patrol_btn"):
                    st.session_state._patrol_pending = True
                    st.rerun()
                # Execute patrol if pending
                if _patrol_pending:
                    config = st.session_state.config
                    system_prompt = build_system_prompt()[0]
                    results = []
                    p0p1 = 0
                    status = st.empty()
                    for u in patrol_urls:
                        status.info(f"巡检中: {u[:60]}...")
                        try:
                            data = scrape(u)
                            if data and not data.get("_scrape_error"):
                                user_msg = format_user_message(data)
                                result = None
                                for event in annotate_one_stream(user_msg, system_prompt, config):
                                    if event["type"] == "result":
                                        result = event["data"]
                                if result and not result.get("error"):
                                    sev = result.get("严重度评级", "")
                                    if sev in ("P0", "P1"):
                                        p0p1 += 1
                                    ir = _do_ingest(data, result, u)
                                    results.append({"url": u, "severity": sev, "action": result.get("分流建议", "?"), "summary": result.get("摘要", "")[:60]})
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

            st.divider()
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
