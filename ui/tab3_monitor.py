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
            platform_labels = {"youtube": "YTB", "xiaohongshu": "小红书", "douyin": "DY",
                              "bilibili": "B站", "weibo": "微博", "wechat": "公众号"}
            rev_map = {v: k for k, v in platform_labels.items()}
            new_platforms_label = st.multiselect(
                "平台", ["YTB", "小红书", "DY", "B站", "微博", "公众号"], key="monitor_new_plat",
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
    harvest = st.session_state.get("monitor_harvest")
    if harvest:
        h = harvest
        st.success(f"Job: {h.job_id} | 获取: {h.total_fetched} | 新增: {h.total_new} | 去重率: {h.dedup_rate:.1%}")

        # ── Per-platform status ──────────────────────────────────────────
        platform_status = {}  # {platform: {"fetched": N, "new": N, "errors": [str]}}
        for kr in h.keyword_results:
            pf = kr.platform
            if pf not in platform_status:
                platform_status[pf] = {"fetched": 0, "new": 0, "errors": []}
            platform_status[pf]["fetched"] += len(kr.date_results) + len(kr.hot_results)
            platform_status[pf]["new"] += len(kr.new_items)
            for r in kr.date_results + kr.hot_results:
                if r.error:
                    platform_status[pf]["errors"].append(f"[{kr.keyword}] {r.error[:100]}")

        if platform_status:
            platform_labels = {"youtube": "YTB", "xiaohongshu": "小红书", "douyin": "DY",
                              "bilibili": "B站", "weibo": "微博", "wechat": "公众号"}
            cols = st.columns(min(len(platform_status), 4))
            for i, (pf, ps) in enumerate(sorted(platform_status.items())):
                label = platform_labels.get(pf, pf)
                with cols[i % 4]:
                    if ps["errors"]:
                        err_preview = ps["errors"][0][:60]
                        st.error(f"✗ {label}: {err_preview}")
                    elif ps["fetched"] > 0:
                        st.success(f"✓ {label}: {ps['fetched']}条")
                    else:
                        st.info(f"- {label}: 0条")

        # ── Notes (date mode, skips, etc.) ──────────────────────────
        all_notes = []
        for kr in h.keyword_results:
            for note in kr.notes:
                all_notes.append(f"[{kr.platform}:{kr.keyword}] {note}")
        if all_notes:
            with st.expander(f"📋 备注 ({len(all_notes)}条)", expanded=False):
                for note in all_notes:
                    st.caption(note)

        # ── Results table with checkboxes ────────────────────────────────
        all_items = []  # (keyword_result, search_result, is_new)
        for kr in h.keyword_results:
            for r in kr.new_items:
                if r.url and not r.error:
                    all_items.append((kr, r, True))
            for r in kr.date_results:
                if r.url and not r.error and r.url not in {x[1].url for x in all_items}:
                    all_items.append((kr, r, False))
            for r in kr.hot_results:
                if r.url and not r.error and r.url not in {x[1].url for x in all_items}:
                    all_items.append((kr, r, False))

        if all_items:
            st.divider()
            st.caption(f"搜索结果 ({len(all_items)}条，含{h.total_new}条新增)")
            col_head1, col_head2 = st.columns([0.05, 0.95])
            with col_head1:
                select_all = st.checkbox("全", key="monitor_select_all",
                                         help="全选/取消全选")
            with col_head2:
                st.caption("勾选要导入录入研判的URL")

            # Sync "全" checkbox → individual checkboxes via session_state.
            # value= only works on first render; on rerun, session_state wins.
            _sel_sync_key = "_monitor_select_all_synced"
            if st.session_state.get(_sel_sync_key) != select_all:
                for i in range(len(all_items)):
                    st.session_state[f"monitor_chk_{i}"] = select_all
                st.session_state[_sel_sync_key] = select_all

            selected_urls = []
            for i, (kr, r, is_new) in enumerate(all_items):
                c1, c2, c3, c4 = st.columns([0.05, 0.45, 0.25, 0.25])
                with c1:
                    checked = st.checkbox(
                        " ", key=f"monitor_chk_{i}",
                        label_visibility="collapsed",
                    )
                    if checked:
                        selected_urls.append(r.url)
                with c2:
                    new_tag = "🆕 " if is_new else ""
                    st.caption(f"{new_tag}{r.title[:80] or '(无标题)'}")
                with c3:
                    pf_label = platform_labels.get(r.platform, r.platform)
                    st.caption(f"{pf_label} | {kr.keyword}")
                with c4:
                    st.caption(r.url[:60] if r.url else "")

            if selected_urls:
                if st.button(f"⚡ 导入并自动研判 ({len(selected_urls)}条)", type="primary",
                             key="monitor_batch_btn", use_container_width=True):
                    st.session_state.entry_queue = list(dict.fromkeys(selected_urls))
                    st.session_state.batch_auto_process = True
                    st.session_state.active_tab = "📝 录入研判"
                    st.rerun()
    else:
        st.info("尚未执行 Monitor 巡检。点击下方按钮启动。")

    col_mode, col_sort, col_btn = st.columns([1, 1, 2])
    with col_mode:
        search_mode = st.selectbox(
            "搜索模式",
            ["按条数", "按日期区间"],
            index=0,
            key="monitor_search_mode",
            help="按条数=原有模式(默认30条); 按日期区间=搜索指定日期内全部内容",
        )
    with col_sort:
        st.selectbox(
            "排序方式",
            ["默认排序", "时间排序"],
            index=0,
            key="monitor_sort_pref",
            help="默认排序=相关性/热度，时间排序=按发布时间",
        )

    date_from_val = ""
    date_to_val = ""
    if search_mode == "按日期区间":
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            date_from_val = st.date_input("开始日期", value=datetime.now(),
                                          key="monitor_date_from")
        with col_d2:
            date_to_val = st.date_input("结束日期", value=datetime.now(),
                                        key="monitor_date_to")
        date_from_val = date_from_val.strftime("%Y-%m-%d") if date_from_val else ""
        date_to_val = date_to_val.strftime("%Y-%m-%d") if date_to_val else ""

    with col_btn:
        if st.button("🔍 执行 Monitor 巡检", key="monitor_run_btn", use_container_width=True):
            with st.spinner("Monitor 巡检中..."):
                try:
                    from agents.monitor import execute_job
                    sort_val = st.session_state.get("monitor_sort_pref", "默认排序")
                    sort_pref = "date" if sort_val == "时间排序" else "default"
                    harvest = execute_job(sort_preference=sort_pref,
                                          date_from=date_from_val,
                                          date_to=date_to_val)
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
