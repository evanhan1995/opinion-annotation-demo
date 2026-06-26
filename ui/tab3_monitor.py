# -*- coding: utf-8 -*-
"""Tab 3: Monitor Dashboard — keyword management, patrol, alerts."""

import json
import streamlit as st
from ui.theme import spacer
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def render_tab3():
    """Render the Monitor dashboard tab matching Figma HTML design."""
    import html as _html

    # ── Helpers ──────────────────────────────────────────────────────
    platform_labels = {"youtube": "YouTube", "xiaohongshu": "小红书", "douyin": "抖音",
                       "bilibili": "B站", "weibo": "微博", "wechat": "公众号"}
    platform_display = ["YouTube", "小红书", "抖音", "B站", "微博", "公众号"]
    rev_map = {v: k for k, v in platform_labels.items()}

    keywords_path = PROJECT_ROOT / "monitor_keywords.json"

    def _load_config():
        cached = st.session_state.get("monitor_cfg")
        if cached is not None:
            return cached
        if keywords_path.exists():
            cfg = json.loads(keywords_path.read_text(encoding="utf-8-sig"))
        else:
            cfg = {"keywords": [], "defaults": {"result_count": 30}}
        st.session_state.monitor_cfg = cfg
        return cfg

    def _save_config(cfg):
        keywords_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        st.session_state.monitor_cfg = cfg

    cfg = _load_config()
    keywords = [kw for kw in cfg.get("keywords", []) if kw.get("active", True)]
    all_keywords = cfg.get("keywords", [])

    # ── Page header (button on right matches Figma) ───────────────────
    hdr_left, hdr_right = st.columns([3, 1])
    with hdr_left:
        st.markdown(
            '<div class="page-header" style="margin-bottom:0;">'
            '<div><h1>Monitor 仪表板</h1>'
            '<div class="subtitle">关键词巡检 · 实时监控 · 舆情预警</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with hdr_right:
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        if st.button("▶ 启动巡检", type="primary", key="monitor_run_top", use_container_width=True):
            with st.spinner("Monitor 巡检中..."):
                try:
                    from agents.monitor import execute_job
                    sort_val = st.session_state.get("monitor_sort_pref", "默认排序")
                    sort_pref = "date" if sort_val == "时间排序" else "default"
                    harvest = execute_job(sort_preference=sort_pref,
                                          date_from="",
                                          date_to="")
                    st.session_state.monitor_harvest = harvest
                    st.rerun()
                except Exception as e:
                    st.error(f"巡检失败: {e}")

    # ── Card 1: Keyword Management ───────────────────────────────────
    st.markdown(
        '<div class="card"><div class="card-title">🔑 关键词管理</div>',
        unsafe_allow_html=True,
    )

    # Add keyword row — input + platform + count + fetch mode + button
    kw_col1, kw_col2, kw_col3, kw_col4, kw_col5 = st.columns(
        [4, 2, 0.9, 1.6, 0.8], vertical_alignment="center")
    with kw_col1:
        new_kw = st.text_input(
            "", placeholder="输入关键词，以逗号分隔",
            label_visibility="collapsed", key="monitor_new_kw",
        )
    with kw_col2:
        new_platforms_label = st.multiselect(
            "平台", platform_display, key="monitor_new_plat", label_visibility="collapsed",
        )
        new_platforms = [rev_map[p] for p in new_platforms_label]
    with kw_col3:
        result_count = st.selectbox(
            "抓取条数", [5, 10, 15, 50], index=2,
            key="monitor_result_count", label_visibility="collapsed",
        )
    with kw_col4:
        fetch_mode_label = st.selectbox(
            "抓取方式", ["默认抓取", "热度抓取", "时间倒序（由近及远）"],
            index=0, key="monitor_fetch_mode", label_visibility="collapsed",
        )
        fetch_mode_map = {"默认抓取": "default", "热度抓取": "hot", "时间倒序（由近及远）": "date"}
    with kw_col5:
        if st.button("添加", key="monitor_add_kw", use_container_width=True):
            if new_kw.strip():
                max_id = max((int(kw["id"].replace("kw", "")) for kw in all_keywords if kw["id"].startswith("kw")), default=0)
                all_keywords.append({
                    "id": f"kw{max_id + 1:03d}",
                    "keyword": new_kw.strip(),
                    "platforms": new_platforms if new_platforms else list(platform_labels.keys()),
                    "result_count": result_count,
                    "fetch_mode": fetch_mode_map.get(fetch_mode_label, "default"),
                    "active": True,
                    "notes": "",
                })
                cfg["keywords"] = all_keywords
                _save_config(cfg)
                st.success(f"已添加: {new_kw.strip()}")
                st.rerun()

    # Render keyword tags as clickable buttons (click = delete)
    if all_keywords:
        # Use columns for horizontal tag layout, max 8 per row
        tags_per_row = min(len(all_keywords), 8)
        tag_cols = st.columns(tags_per_row)
        for i, kw in enumerate(all_keywords):
            col_idx = i % tags_per_row
            with tag_cols[col_idx]:
                if st.button(
                    f"{kw['keyword']}  ✕",
                    key=f"monitor_tag_{kw['id']}",
                    help=f"点击删除「{kw['keyword']}」",
                    use_container_width=True,
                ):
                    all_keywords.pop(i)
                    cfg["keywords"] = all_keywords
                    _save_config(cfg)
                    st.success(f"已删除「{kw['keyword']}」")
                    st.rerun()

    # Platform select pills
    active_platforms = set()
    for kw in keywords:
        active_platforms.update(kw.get("platforms", []))
    all_platforms = ["全选"] + [platform_labels.get(p, p) for p in
                    ["youtube", "xiaohongshu", "douyin", "bilibili", "weibo", "wechat"]]
    platform_html = '<div class="platform-select">'
    for pf in all_platforms:
        is_active = " active" if pf == "全选" or pf in [platform_labels.get(p, p) for p in active_platforms] else ""
        platform_html += f'<span class="platform-opt{is_active}">{_html.escape(pf)}</span>'
    platform_html += '</div>'
    st.markdown(platform_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)  # close card

    # ── Card 2: Patrol Indicators ────────────────────────────────────
    harvest = st.session_state.get("monitor_harvest")
    if harvest:
        h = harvest
        indicator_html = (
            '<div class="card"><div class="card-title">📈 巡检指标</div>'
            '<div class="indicator-row">'
            f'<div class="indicator-item"><div class="val">{h.total_fetched + h.total_new}</div><div class="lbl">监测总数</div></div>'
            f'<div class="indicator-item"><div class="val" style="color:#dc2626;">{h.total_new}</div><div class="lbl">新增预警</div></div>'
            f'<div class="indicator-item"><div class="val">{len(h.keyword_results)}</div><div class="lbl">巡检轮次</div></div>'
            f'<div class="indicator-item"><div class="val">{h.dedup_rate:.0%}</div><div class="lbl">去重率</div></div>'
            f'<div class="indicator-item"><div class="val">{len(keywords)}</div><div class="lbl">活动关键词</div></div>'
            '</div></div>'
        )
        st.markdown(indicator_html, unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="card"><div class="card-title">📈 巡检指标</div>'
            '<div class="indicator-row">'
            f'<div class="indicator-item"><div class="val">—</div><div class="lbl">监测总数</div></div>'
            f'<div class="indicator-item"><div class="val" style="color:#dc2626;">—</div><div class="lbl">新增预警</div></div>'
            f'<div class="indicator-item"><div class="val">{len(keywords)}</div><div class="lbl">活动关键词</div></div>'
            f'<div class="indicator-item"><div class="val">{len(set(p for kw in keywords for p in kw.get("platforms", [])))}</div><div class="lbl">覆盖平台</div></div>'
            f'<div class="indicator-item"><div class="val">—</div><div class="lbl">上次巡检</div></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

    # ── Card 3: Patrol Results ───────────────────────────────────────
    harvest = st.session_state.get("monitor_harvest")
    if harvest:
        h = harvest

        # Build results list (same logic as before)
        all_items = []
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
            st.markdown(
                '<div class="card"><div class="card-title">📋 巡检结果</div>'
                f'<p style="font-size:13px;color:#64748B;margin-bottom:12px;">'
                f'Job: {_html.escape(str(h.job_id))} | 获取: {h.total_fetched} | 新增: {h.total_new} | 去重率: {h.dedup_rate:.1%}'
                f'</p>',
                unsafe_allow_html=True,
            )

            # ── Multi-filter panel ──────────────────────────────────────
            # Initialize filter state
            if "monitor_filters" not in st.session_state:
                st.session_state.monitor_filters = {}

            # Extract dynamic filter options from current data
            platforms_in_data = sorted(set(
                platform_labels.get(r.platform, r.platform)
                for _, r, _ in all_items
            ))
            keywords_in_data = sorted(set(kr.keyword for kr, _, _ in all_items))

            def _get_severity_display(r):
                v = getattr(r, 'severity', None)
                return v if v else '未知'

            def _get_heat_display(r):
                v = getattr(r, 'heat', None)
                return '有' if v else '未知'

            def _get_time_display(r):
                v = getattr(r, 'time', None) or getattr(r, 'publish_time', None)
                return '有' if v else '未知'

            def _matches_filters(item, f):
                kr, r, is_new = item
                if f.get("platform"):
                    if platform_labels.get(r.platform, r.platform) not in f["platform"]:
                        return False
                if f.get("severity"):
                    if _get_severity_display(r) not in f["severity"]:
                        return False
                if f.get("status"):
                    status = "新增" if is_new else "已标记"
                    if status not in f["status"]:
                        return False
                if f.get("keyword"):
                    if kr.keyword not in f["keyword"]:
                        return False
                if f.get("heat"):
                    if _get_heat_display(r) not in f["heat"]:
                        return False
                if f.get("time"):
                    if _get_time_display(r) not in f["time"]:
                        return False
                return True

            filters = st.session_state.monitor_filters
            active_count = sum(1 for v in filters.values() if v)
            badge = f" ({active_count}项激活)" if active_count else ""

            with st.expander(f"🔍 多条件筛选{badge}", expanded=False):
                r1c1, r1c2, r1c3 = st.columns(3)
                r2c1, r2c2, r2c3 = st.columns(3)
                with r1c1:
                    st.multiselect(
                        "平台", platforms_in_data,
                        default=filters.get("platform", []),
                        key="filter_platform", label_visibility="collapsed",
                        placeholder="全部平台",
                    )
                with r1c2:
                    st.multiselect(
                        "严重度", ["P0", "P1", "P2", "P3", "未知"],
                        default=filters.get("severity", []),
                        key="filter_severity", label_visibility="collapsed",
                        placeholder="全部严重度",
                    )
                with r1c3:
                    st.multiselect(
                        "状态", ["新增", "已标记"],
                        default=filters.get("status", []),
                        key="filter_status", label_visibility="collapsed",
                        placeholder="全部状态",
                    )
                with r2c1:
                    st.multiselect(
                        "匹配关键词", keywords_in_data,
                        default=filters.get("keyword", []),
                        key="filter_keyword", label_visibility="collapsed",
                        placeholder="全部关键词",
                    )
                with r2c2:
                    st.multiselect(
                        "热度", ["有", "未知"],
                        default=filters.get("heat", []),
                        key="filter_heat", label_visibility="collapsed",
                        placeholder="全部",
                    )
                with r2c3:
                    st.multiselect(
                        "时间", ["有", "未知"],
                        default=filters.get("time", []),
                        key="filter_time", label_visibility="collapsed",
                        placeholder="全部",
                    )

                btn_c1, btn_c2, _ = st.columns([1, 1, 4])
                with btn_c1:
                    if st.button("应用筛选", use_container_width=True, key="apply_filter"):
                        st.session_state.monitor_filters = {
                            "platform": st.session_state.get("filter_platform", []),
                            "severity": st.session_state.get("filter_severity", []),
                            "status": st.session_state.get("filter_status", []),
                            "keyword": st.session_state.get("filter_keyword", []),
                            "heat": st.session_state.get("filter_heat", []),
                            "time": st.session_state.get("filter_time", []),
                        }
                        st.session_state.monitor_page = 0
                        st.rerun()
                with btn_c2:
                    if st.button("重置", use_container_width=True, key="reset_filter"):
                        st.session_state.monitor_filters = {}
                        st.session_state.monitor_page = 0
                        st.rerun()

            # Apply filters
            filtered_items = [it for it in all_items if _matches_filters(it, filters)]

            # Track selections across pages via session state
            if "monitor_selected_urls" not in st.session_state:
                st.session_state.monitor_selected_urls = set()

            # Page state
            PAGE_SIZE = 15
            if "monitor_page" not in st.session_state:
                st.session_state.monitor_page = 0
            total_pages = max(1, (len(filtered_items) + PAGE_SIZE - 1) // PAGE_SIZE)
            if st.session_state.monitor_page >= total_pages:
                st.session_state.monitor_page = 0

            start_idx = st.session_state.monitor_page * PAGE_SIZE
            end_idx = min(start_idx + PAGE_SIZE, len(filtered_items))
            page_items = filtered_items[start_idx:end_idx]

            # Empty result fallback
            if not filtered_items:
                st.markdown(
                    '<p style="font-size:14px;color:#64748B;padding:16px 0;text-align:center;">'
                    '无匹配结果，请调整筛选条件</p>',
                    unsafe_allow_html=True,
                )
                st.markdown('</div>', unsafe_allow_html=True)  # close card
                # Still render the rest (alerts, etc.)
                if harvest:
                    all_notes = []
                    for kr in h.keyword_results:
                        for note in kr.notes:
                            all_notes.append(f"[{kr.platform}:{kr.keyword}] {note}")
                    if all_notes:
                        with st.expander(f"📋 备注 ({len(all_notes)}条)", expanded=False):
                            for note in all_notes:
                                st.caption(note)
                alerts = st.session_state.get("p0p1_alerts", [])
                if alerts:
                    st.divider()
                    with st.expander(f"🚨 高优告警 ({len(alerts)})", expanded=bool(alerts)):
                        for alert in alerts:
                            sev = alert.get("severity", "?")
                            color = "red" if sev == "P0" else "orange"
                            st.markdown(f":{color}[{sev}] **{alert.get('title', '?')[:60]}** — {alert.get('platform', '?')}")
                return

            # Table header
            hd_cols = st.columns([0.1, 3.5, 1, 0.8, 0.8, 1.2, 0.7, 1.5])
            headers = ["", "标题", "平台", "严重度", "状态", "匹配关键词", "热度", "时间"]
            for hc, hdr in zip(hd_cols, headers):
                with hc:
                    st.caption(hdr)

            # Select-all checkbox — sync to individual checkboxes on this page
            _sel_key = "monitor_select_all"
            st.checkbox(
                "全选本页", key=_sel_key,
                help="全选/取消全选当前页",
            )
            if st.session_state.get(_sel_key):
                for _, r, _ in page_items:
                    st.session_state.monitor_selected_urls.add(r.url)
            else:
                for _, r, _ in page_items:
                    st.session_state.monitor_selected_urls.discard(r.url)

            st.divider()

            # Table rows with individual checkboxes
            for global_idx, (kr, r, is_new) in enumerate(page_items):
                url = r.url
                row_cols = st.columns([0.1, 3.5, 1, 0.8, 0.8, 1.2, 0.7, 1.5])
                with row_cols[0]:
                    checked = st.checkbox(
                        "选择",
                        value=(url in st.session_state.monitor_selected_urls),
                        key=f"monitor_sel_{start_idx + global_idx}",
                        label_visibility="collapsed",
                    )
                    if checked:
                        st.session_state.monitor_selected_urls.add(url)
                    else:
                        st.session_state.monitor_selected_urls.discard(url)
                with row_cols[1]:
                    title = (getattr(r, 'title', '') or '无标题')[:50]
                    st.markdown(
                        f'<a href="{_html.escape(r.url)}" target="_blank" '
                        f'style="text-decoration:none;color:#1565C0;" '
                        f'title="{_html.escape(r.url)}">{_html.escape(title)}</a>',
                        unsafe_allow_html=True,
                    )
                with row_cols[2]:
                    st.caption(platform_labels.get(r.platform, r.platform))
                with row_cols[3]:
                    sev = getattr(r, 'severity', '') or ''
                    st.caption(sev)
                with row_cols[4]:
                    status = "新增" if is_new else "已标记"
                    st.caption(status)
                with row_cols[5]:
                    st.caption(kr.keyword)
                with row_cols[6]:
                    heat = getattr(r, 'heat', '') or ''
                    st.caption(str(heat))
                with row_cols[7]:
                    time_str = getattr(r, 'time', '') or ''
                    st.caption(str(time_str))
                st.divider()

            # Pagination controls
            st.caption(f"显示 {start_idx + 1}-{end_idx} 条，共 {len(filtered_items)} 条 (含{h.total_new}条新增)" + (f" [筛选自{len(all_items)}条]" if len(filtered_items) != len(all_items) else ""))
            pc1, pc2, pc3, pc4, pc5 = st.columns([1, 1, 3, 1, 1], vertical_alignment="center")
            with pc1:
                if st.button("⬅ 上一页", disabled=(st.session_state.monitor_page == 0),
                          key="monitor_prev_page", use_container_width=True):
                    st.session_state.monitor_page -= 1
                    st.rerun()
            with pc2:
                if st.button("下一页 ➡", disabled=(st.session_state.monitor_page >= total_pages - 1),
                          key="monitor_next_page", use_container_width=True):
                    st.session_state.monitor_page += 1
                    st.rerun()
            with pc3:
                st.caption(f"第 {st.session_state.monitor_page + 1}/{total_pages} 页")

            # Batch import button
            selected_urls = list(st.session_state.monitor_selected_urls)
            if selected_urls:
                if st.button(
                    f"⚡ 导入并自动研判 ({len(selected_urls)}条)",
                    type="primary", key="monitor_batch_btn", use_container_width=True,
                ):
                    st.session_state.entry_queue = list(dict.fromkeys(selected_urls))
                    st.session_state.batch_auto_process = True
                    st.session_state._pending_tab = "录入研判"
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)  # close card

        else:
            # Harvest exists but no displayable items
            st.markdown(
                '<div class="card"><div class="card-title">📋 巡检结果</div>'
                f'<p style="font-size:13px;color:#64748B;margin-bottom:12px;">'
                f'Job: {_html.escape(str(h.job_id))} | 获取: {h.total_fetched} | 新增: {h.total_new}'
                f'</p>'
                f'<p style="font-size:14px;color:#64748B;padding:16px 0;">本轮未发现新内容，所有结果已去重。</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

    else:
        st.markdown(
            '<div class="card"><div class="card-title">📋 巡检结果</div>'
            '<p style="font-size:14px;color:#64748B;padding:16px 0;">'
            '尚未执行 Monitor 巡检。点击右上角 ▶ 启动巡检 按钮启动。</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Per-platform errors ──────────────────────────────────────────
    if harvest:
        h = harvest
        platform_status = {}
        for kr in h.keyword_results:
            pf = kr.platform
            if pf not in platform_status:
                platform_status[pf] = {"fetched": 0, "new": 0, "errors": []}
            platform_status[pf]["fetched"] += len(kr.date_results) + len(kr.hot_results)
            platform_status[pf]["new"] += len(kr.new_items)
            for r in kr.date_results + kr.hot_results:
                if r.error:
                    platform_status[pf]["errors"].append(f"[{kr.keyword}] {r.error[:100]}")

        all_notes = []
        for kr in h.keyword_results:
            for note in kr.notes:
                all_notes.append(f"[{kr.platform}:{kr.keyword}] {note}")

        if all_notes:
            with st.expander(f"📋 备注 ({len(all_notes)}条)", expanded=False):
                for note in all_notes:
                    st.caption(note)

    # ── P0/P1 alerts ─────────────────────────────────────────────────
    alerts = st.session_state.get("p0p1_alerts", [])
    if alerts:
        st.divider()
        with st.expander(f"🚨 高优告警 ({len(alerts)})", expanded=bool(alerts)):
            for alert in alerts:
                sev = alert.get("severity", "?")
                color = "red" if sev == "P0" else "orange"
                st.markdown(f":{color}[{sev}] **{alert.get('title', '?')[:60]}** — {alert.get('platform', '?')}")
