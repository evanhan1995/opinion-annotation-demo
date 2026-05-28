# -*- coding: utf-8 -*-
"""Tab 3: Monitor Dashboard — keyword management, patrol, alerts."""

import json
import streamlit as st
from ui.theme import spacer
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def render_tab3():
    """Render the Monitor dashboard tab."""
    st.subheader("📡 Monitor 仪表板")

    keywords_path = PROJECT_ROOT / "monitor_keywords.json"

    # ── Helper: load config ───────────────────────────────────────────
    def _load_config():
        if keywords_path.exists():
            return json.loads(keywords_path.read_text(encoding="utf-8"))
        return {"keywords": [], "defaults": {"result_count": 30}}

    def _save_config(cfg):
        keywords_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg = _load_config()
    keywords = [kw for kw in cfg.get("keywords", []) if kw.get("active", True)]
    all_keywords = cfg.get("keywords", [])

    # ── Keyword management ────────────────────────────────────────────
    with st.expander("➕ 管理关键词", expanded=False):
        col_kw, col_plat, col_count, col_btn = st.columns([2, 2, 1, 1])
        with col_kw:
            new_kw = st.text_input("关键词", placeholder="输入新关键词...", key="monitor_new_kw")
        with col_plat:
            platform_labels = {"youtube": "YTB", "xiaohongshu": "小红书", "douyin": "DY"}
            rev_map = {v: k for k, v in platform_labels.items()}
            new_platforms_label = st.multiselect(
                "平台", ["YTB", "小红书", "DY"], key="monitor_new_plat",
            )
            new_platforms = [rev_map[p] for p in new_platforms_label]
        with col_count:
            count_options = [10, 15, 30]
            result_count = st.selectbox(
                "抓取数量", count_options,
                index=count_options.index(cfg["defaults"]["result_count"]) if cfg["defaults"]["result_count"] in count_options else 2,
                key="monitor_new_count",
            )
        with col_btn:
            spacer()  # align
            if st.button("添加", key="monitor_add_kw", use_container_width=True):
                if new_kw.strip() and new_platforms:
                    max_id = max((int(kw["id"].replace("kw", "")) for kw in all_keywords if kw["id"].startswith("kw")), default=0)
                    all_keywords.append({
                        "id": f"kw{max_id + 1:03d}",
                        "keyword": new_kw.strip(),
                        "platforms": new_platforms,
                        "result_count": result_count,
                        "active": True,
                        "notes": "",
                    })
                    cfg["keywords"] = all_keywords
                    _save_config(cfg)
                    st.success(f"已添加: {new_kw.strip()}")
                    st.rerun()

        if all_keywords:
            st.divider()
            st.caption("已有关键词（点击删除）")
            for i, kw in enumerate(all_keywords):
                kw_col1, kw_col2, kw_col3, kw_col4 = st.columns([3, 2, 1, 1])
                with kw_col1:
                    st.caption(kw["keyword"])
                with kw_col2:
                    pf_display = ", ".join(platform_labels.get(p, p) for p in kw.get("platforms", []))
                    st.caption(pf_display)
                with kw_col3:
                    status = "✅" if kw.get("active", True) else "⏸️"
                    st.caption(status)
                with kw_col4:
                    if st.button("🗑️", key=f"monitor_del_{kw['id']}", help=f"删除 {kw['keyword']}"):
                        all_keywords.pop(i)
                        cfg["keywords"] = all_keywords
                        _save_config(cfg)
                        st.rerun()

    col1, col2, col3 = st.columns(3)
    col1.metric("活动关键词", len(keywords))
    col2.metric("覆盖平台", len(set(p for kw in keywords for p in kw.get("platforms", []))))
    col3.metric("默认抓取数", cfg["defaults"]["result_count"])

    # Keyword list
    if keywords:
        with st.expander(f"关键词列表 ({len(keywords)})", expanded=True):
            rows = []
            for kw in keywords:
                platforms = ", ".join(platform_labels.get(p, p) for p in kw.get("platforms", []))
                count = kw.get("result_count", cfg["defaults"]["result_count"])
                rows.append(f"| {kw['id']} | {kw['keyword']} | {platforms} | {count} |")
            st.markdown("| ID | 关键词 | 平台 | 抓取数 |\n|---|---|---|---|\n" + "\n".join(rows))

    # Last job status
    st.divider()
    st.subheader("最近巡检")
    if st.session_state.get("monitor_harvest"):
        h = st.session_state.monitor_harvest
        st.success(f"Job: {h.job_id} | 获取: {h.total_fetched} | 新增: {h.total_new} | 去重率: {h.dedup_rate:.1%}")
    else:
        st.info("尚未执行 Monitor 巡检。点击下方按钮启动。")

    col_sort, col_btn = st.columns([1, 2])
    with col_sort:
        st.selectbox(
            "排序方式",
            ["默认排序", "时间排序"],
            index=0,
            key="monitor_sort_pref",
            help="默认排序=相关性/热度，时间排序=按发布时间",
        )
    with col_btn:
        if st.button("🔍 执行 Monitor 巡检", key="monitor_run_btn", use_container_width=True):
            with st.spinner("Monitor 巡检中..."):
                try:
                    from agents.monitor import execute_job
                    sort_val = st.session_state.get("monitor_sort_pref", "默认排序")
                    sort_pref = "date" if sort_val == "时间排序" else "default"
                    harvest = execute_job(sort_preference=sort_pref)
                    st.session_state.monitor_harvest = harvest
                    st.rerun()
                except Exception as e:
                    st.error(f"巡检失败: {e}")

    # P0/P1 alerts
    if st.session_state.get("p0p1_alerts"):
        st.divider()
        st.subheader(f"🚨 高优告警 ({len(st.session_state.p0p1_alerts)})")
        for alert in st.session_state.p0p1_alerts:
            sev = alert.get("severity", "?")
            color = "red" if sev == "P0" else "orange"
            st.markdown(f":{color}[{sev}] **{alert.get('title', '?')[:60]}** — {alert.get('platform', '?')}")
