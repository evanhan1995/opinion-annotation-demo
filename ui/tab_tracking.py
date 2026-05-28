# -*- coding: utf-8 -*-
"""High-risk tracking tab — continuous monitoring of viral/harmful content."""

import json
import time as _time_module
from datetime import datetime

import streamlit as st

from engine.tracker import (
    add_tracking_case,
    check_alerts,
    compute_delta,
    get_all_enabled_cases,
    get_case_by_id,
    get_case_history,
    get_tracking_status,
    load_tracking_cases,
    remove_tracking_case,
    save_tracking_cases,
    scrape_and_record,
    update_tracking_case,
)

METRIC_LABELS = {"浏览": "views", "评论": "comments", "点赞": "likes", "收藏": "shares"}
METRIC_REVERSE = {v: k for k, v in METRIC_LABELS.items()}

INTERVAL_OPTIONS = [
    "15分钟", "30分钟", "1小时", "2小时", "4小时", "6小时", "8小时",
]
INTERVAL_MINUTES = {
    "15分钟": 15, "30分钟": 30, "1小时": 60, "2小时": 120,
    "4小时": 240, "6小时": 360, "8小时": 480,
}
INTERVAL_REVERSE = {v: k for k, v in INTERVAL_MINUTES.items()}


def render_tab_tracking():
    """Render the high-risk tracking tab."""
    st.subheader("⚠️ 高危追踪")
    st.caption("对高风险舆情进行持续、高频的抓取核查，追踪舆情变化，防止恶化")

    # ── Debug / status bar ─────────────────────────────────────────
    ts = get_tracking_status()
    if ts.get("running"):
        st.caption(f"⏱ 追踪调度器: 运行中 | 活跃案例: {ts.get('active_cases', 0)}")
    else:
        st.caption("⏱ 追踪调度器: 待启动 (启动值守后自动激活)")

    st.divider()

    # ── Add new tracking case ──────────────────────────────────────
    with st.expander("➕ 添加新追踪", expanded=False):
        with st.form("add_tracking_form", clear_on_submit=True):
            new_url = st.text_input("舆情链接", placeholder="https://...", key="track_new_url")
            new_label = st.text_input("标签（可选）", placeholder="描述此舆情...", key="track_new_label")
            new_interval = st.selectbox(
                "抓取间隔", INTERVAL_OPTIONS, index=3,  # default 2h
                key="track_new_interval",
                help="最短 15 分钟，最长 8 小时",
            )
            submitted = st.form_submit_button("添加追踪", use_container_width=True)
            if submitted and new_url.strip():
                interval_min = INTERVAL_MINUTES[new_interval]
                case_id = add_tracking_case(
                    new_url.strip(),
                    label=new_label.strip() or new_url.strip()[:60],
                    interval_minutes=interval_min,
                )
                st.success(f"已添加追踪案例: {case_id}")
                st.rerun()

    # ── Tracking case list ─────────────────────────────────────────
    cases = load_tracking_cases()
    if not cases:
        st.info("暂无追踪案例。点击上方「添加新追踪」开始。")
        return

    # Sort: newest first
    cases.sort(key=lambda c: c.get("created_at", ""), reverse=True)

    for case in cases:
        _render_tracking_case(case)


def _render_tracking_case(case: dict):
    """Render a single tracking case expander with metrics, charts, alerts, settings."""
    case_id = case["id"]
    url = case.get("url", "")
    label = case.get("label", case_id)
    platform = case.get("platform", "?")
    enabled = case.get("enabled", True)
    interval_min = case.get("interval_minutes", 120)
    alerts_cfg = case.get("alerts", [])

    status_icon = "🟢" if enabled else "⚫"
    expander_label = f"{status_icon} {case_id} — {label[:50]}"

    with st.expander(expander_label, expanded=(case == load_tracking_cases()[0])):
        st.caption(f"链接: {url}")
        st.caption(f"平台: {platform} | 抓取间隔: {INTERVAL_REVERSE.get(interval_min, f'{interval_min}分钟')} | 启用: {enabled}")

        history = get_case_history(case_id)
        last_ts = history[-1]["ts"] if history else "从未抓取"
        st.caption(f"上次抓取: {last_ts[:19] if len(last_ts) > 19 else last_ts}")

        # ── Metrics display ────────────────────────────────────────
        if history:
            delta = compute_delta(case_id)
            latest = history[-1]

            st.markdown("#### 📊 社媒流量数据")

            mc1, mc2, mc3, mc4 = st.columns(4)
            _metric_card(mc1, "播放量", latest.get("views", 0), delta.get("views") if delta else None)
            _metric_card(mc2, "点赞", latest.get("likes", 0), delta.get("likes") if delta else None)
            _metric_card(mc3, "评论", latest.get("comments", 0), delta.get("comments") if delta else None)
            _metric_card(mc4, "收藏/分享", latest.get("shares", 0), delta.get("shares") if delta else None)

            # ── History chart ──────────────────────────────────────
            if len(history) >= 2:
                st.markdown("#### 📈 流量趋势")
                try:
                    import pandas as pd
                    df = pd.DataFrame(history)
                    df["ts"] = pd.to_datetime(df["ts"])
                    df = df.set_index("ts")
                    chart_data = df[["views", "likes", "comments", "shares"]].fillna(0)
                    # Only show columns that have non-zero data
                    cols = [c for c in ["views", "likes", "comments", "shares"] if chart_data[c].sum() > 0]
                    if cols:
                        st.line_chart(chart_data[cols])
                except Exception:
                    st.caption("图表加载失败")
        else:
            st.caption("📊 暂无数据，点击「立即抓取」获取首次数据")

        # ── Action buttons ─────────────────────────────────────────
        bc1, bc2, bc3, bc4 = st.columns(4)
        with bc1:
            if st.button("🔄 立即抓取", key=f"track_fetch_{case_id}", use_container_width=True):
                with st.spinner(f"抓取中: {url[:60]}..."):
                    result = scrape_and_record(case_id, force=True)
                if result and not result.get("_error"):
                    # Check alerts after scrape
                    triggered = check_alerts(case_id)
                    if triggered:
                        try:
                            from shared.notify import send_feishu_card
                        except ImportError:
                            send_feishu_card = None
                        for t in triggered:
                            if send_feishu_card:
                                send_feishu_card(
                                    title=f"⚠️ 高危追踪告警 — {t['case_label'][:40]}",
                                    body_text=(
                                        f"**{t['metric_label']}** 增长 **{t['growth_pct']}%**，"
                                        f"超过阈值 **{int(t['threshold']*100)}%**\n"
                                        f"当前: {t['curr']:,} | 上次: {t['prev']:,}\n"
                                        f"链接: {t['url']}"
                                    ),
                                    level="warning",
                                )
                            st.warning(
                                f"⚠️ 告警触发: {t['metric_label']} 增长 {t['growth_pct']}% "
                                f"(阈值 {int(t['threshold']*100)}%)"
                            )
                    st.success("抓取完成")
                else:
                    err = (result or {}).get("_error", "抓取失败")
                    st.error(f"抓取失败: {err}")
                st.rerun()
        with bc2:
            toggle_label = "⏸ 暂停" if enabled else "▶ 启用"
            if st.button(toggle_label, key=f"track_toggle_{case_id}", use_container_width=True):
                update_tracking_case(case_id, {"enabled": not enabled})
                st.rerun()
        with bc3:
            if st.button("🗑 删除", key=f"track_del_{case_id}", use_container_width=True):
                remove_tracking_case(case_id)
                st.success(f"已删除 {case_id}")
                st.rerun()

        # ── Alert settings ─────────────────────────────────────────
        st.divider()
        st.markdown("#### ⚙️ 告警设置")
        _render_alert_settings(case)

        # ── Interval settings ──────────────────────────────────────
        st.divider()
        st.markdown("#### ⏱ 抓取间隔")
        cur_interval_label = INTERVAL_REVERSE.get(interval_min, "2小时")
        new_interval_label = st.selectbox(
            "搜索间隔",
            INTERVAL_OPTIONS,
            index=INTERVAL_OPTIONS.index(cur_interval_label) if cur_interval_label in INTERVAL_OPTIONS else 3,
            key=f"track_interval_{case_id}",
            help="每条案例的独立抓取间隔（15分钟 ~ 8小时）",
        )
        new_interval_min = INTERVAL_MINUTES[new_interval_label]

        # ── Save all settings ──────────────────────────────────────
        with bc4:
            if st.button("💾 保存设置", key=f"track_save_{case_id}", use_container_width=True):
                update_tracking_case(case_id, {
                    "interval_minutes": new_interval_min,
                    "alerts": st.session_state.get(f"_track_alerts_{case_id}", alerts_cfg),
                })
                st.success("设置已保存")
                _time_module.sleep(0.5)
                st.rerun()


def _metric_card(col, label: str, value: int, delta_info: dict | None):
    """Render a single metric card with optional delta."""
    val_str = f"{value:,}" if value else "—"
    if delta_info and delta_info.get("delta_pct") is not None:
        dp = delta_info["delta_pct"]
        arrow = "▲" if dp > 0 else ("▼" if dp < 0 else "▬")
        delta_str = f"{arrow} {dp:+.1f}%"
        col.metric(label, val_str, delta=delta_str)
    else:
        col.metric(label, val_str)


def _render_alert_settings(case: dict):
    """Render the per-case alert rule editor."""
    case_id = case["id"]
    alerts_key = f"_track_alerts_{case_id}"

    # Initialise from case config
    if alerts_key not in st.session_state:
        st.session_state[alerts_key] = list(case.get("alerts", []))

    alerts = st.session_state[alerts_key]

    # Render existing rules
    to_delete = None
    for i, alert in enumerate(alerts):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            cur_metric = alert.get("metric", "views")
            cur_label = METRIC_REVERSE.get(cur_metric, "浏览")
            new_label = st.selectbox(
                "观察点", list(METRIC_LABELS.keys()),
                index=list(METRIC_LABELS.keys()).index(cur_label) if cur_label in METRIC_LABELS else 0,
                key=f"track_alert_metric_{case_id}_{i}",
                label_visibility="collapsed",
            )
            alert["metric"] = METRIC_LABELS[new_label]
        with c2:
            cur_threshold = alert.get("threshold", 0.5)
            thresh_label = "50%" if cur_threshold == 0.5 else "100%"
            new_thresh_label = st.selectbox(
                "触发条件", ["50%", "100%"],
                index=["50%", "100%"].index(thresh_label) if thresh_label in ["50%", "100%"] else 0,
                key=f"track_alert_thresh_{case_id}_{i}",
                label_visibility="collapsed",
            )
            alert["threshold"] = 0.5 if new_thresh_label == "50%" else 1.0
        with c3:
            if st.button("✕", key=f"track_alert_del_{case_id}_{i}"):
                to_delete = i

    if to_delete is not None:
        alerts.pop(to_delete)
        st.session_state[alerts_key] = alerts
        st.rerun()

    # Add new rule button
    if st.button("+ 新增观察点", key=f"track_alert_add_{case_id}"):
        alerts.append({"metric": "views", "threshold": 0.5})
        st.session_state[alerts_key] = alerts
        st.rerun()

    if not alerts:
        st.caption("暂无告警规则，点击「新增观察点」添加")
