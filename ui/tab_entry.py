# -*- coding: utf-8 -*-
"""Tab: 录入研判 — merged manual entry + URL scraping + auto-annotate.

Layout order:
  1. URL input row + 抓取标注 button
  2. TXT file upload + AI summary
  3. Social media data (always visible, no expander)
  4. Classification & rating fields
  5. Summary + reason
  6. Save buttons
  7. Annotation result display
"""

import html
from datetime import date as _date
from pathlib import Path as _Path

import streamlit as st
from engine.annotate import (
    annotate_one_stream,
    build_system_prompt,
    format_user_message,
    CATEGORY_OPTIONS,
)
from engine.scraper import _detect_platform, scrape
from ui.theme import spacer
from ui.shared import (
    _clear_correction_widgets,
    _convert_wikilinks,
    _do_ingest,
    _render_annotation_result,
    _save_annotation_output,
    do_scrape,
)

TAB_KEY = "entry_"


SEV_COLORS = {"P0": "#dc3545", "P1": "#fd7e14", "P2": "#ffc107", "P3": "#28a745"}


def _render_batch_review():
    """Render batch review UI with collapsible cards."""
    items = st.session_state.batch_items
    success_count = sum(1 for it in items if it["status"] == "success")
    failed_count = sum(1 for it in items if it["status"] == "failed")
    unsaved = sum(1 for it in items if it["status"] == "success" and not it["saved"])

    st.subheader(f"📋 批量审核 ({success_count}/{len(items)} 成功, {failed_count} 失败)")

    if failed_count:
        st.caption(f"⚠️ {failed_count} 条处理失败, 请检查后重试")

    st.divider()

    for i, item in enumerate(items):
        if item["status"] == "success":
            ann = item["annotation"] or {}
            sev = ann.get("严重度评级", "?")
            action = ann.get("分流建议", "?")
            title = item.get("title", "")[:60] or item["url"][:60]
            color = SEV_COLORS.get(sev, "#6c757d")
            saved_badge = " ✅已保存" if item["saved"] else ""

            expander_label = f"{item['platform']} | {sev} | {action} | {title}{saved_badge}"

            with st.expander(expander_label, expanded=False):
                if item["saved"]:
                    st.info("此条目已保存到知识库")
                    continue

                # Quick edit row
                q1, q2 = st.columns(2)
                with q1:
                    new_sev = st.selectbox(
                        "严重度评级", ["P0", "P1", "P2", "P3"],
                        index=["P0", "P1", "P2", "P3"].index(sev) if sev in ["P0", "P1", "P2", "P3"] else 2,
                        key=f"batch_sev_{i}",
                    )
                with q2:
                    new_action = st.selectbox(
                        "分流建议", ["立即处理", "持续观察", "可忽略", "正面可利用"],
                        index=["立即处理", "持续观察", "可忽略", "正面可利用"].index(action) if action in ["立即处理", "持续观察", "可忽略", "正面可利用"] else 1,
                        key=f"batch_action_{i}",
                    )

                new_summary = st.text_area(
                    "摘要", value=ann.get("摘要", ""), key=f"batch_summary_{i}",
                )

                # Full edit (inner expander)
                with st.expander("完整编辑", expanded=False):
                    sent = ann.get("情感分析", {}).get("整体情感", "中性") if ann.get("情感分析") else "中性"
                    sent_options = ["正面", "负面", "中性", "混合"]
                    new_sent = st.selectbox(
                        "整体情感", sent_options,
                        index=sent_options.index(sent) if sent in sent_options else 2,
                        key=f"batch_sent_{i}",
                    )

                    cats = [c for c in (ann.get("舆情分类", []) or []) if c in CATEGORY_OPTIONS]
                    new_cats = st.multiselect(
                        "舆情分类", CATEGORY_OPTIONS, default=cats, key=f"batch_cats_{i}",
                    )

                    new_reason = st.text_area(
                        "严重度理由", value=ann.get("严重度理由", ""), key=f"batch_reason_{i}",
                    )

                    scraped = item.get("scraped_data") or {}
                    if scraped:
                        st.caption("原始数据")
                        st.json(scraped)

                # Per-item save
                if st.button("💾 确认保存", key=f"batch_save_{i}", type="primary"):
                    # Apply edits
                    item["annotation"]["严重度评级"] = new_sev
                    item["annotation"]["分流建议"] = new_action
                    item["annotation"]["摘要"] = new_summary
                    item["annotation"]["情感分析"] = item["annotation"].get("情感分析", {})
                    item["annotation"]["情感分析"]["整体情感"] = new_sent
                    item["annotation"]["舆情分类"] = new_cats
                    item["annotation"]["严重度理由"] = new_reason

                    _save_annotation_output(item["scraped_data"], item["annotation"], item["url"])
                    st.session_state.ingest_result = _do_ingest(
                        item["scraped_data"], item["annotation"], item["url"],
                    )
                    item["saved"] = True
                    st.rerun()

        elif item["status"] == "failed":
            with st.expander(f"❌ 失败 | {item.get('platform', '未知')} | {item['url'][:50]}...", expanded=False):
                st.error(item.get("error", "未知错误"))
                st.caption(f"URL: {item['url']}")

    # Bottom actions
    st.divider()
    bc1, bc2 = st.columns([2, 1])
    with bc1:
        if st.button(
            f"💾 全部保存到知识库 ({unsaved}条未保存)",
            type="primary", use_container_width=True, disabled=unsaved == 0,
            key="batch_save_all",
        ):
            for i, item in enumerate(items):
                if item["status"] == "success" and not item["saved"]:
                    _save_annotation_output(item["scraped_data"], item["annotation"], item["url"])
                    st.session_state.ingest_result = _do_ingest(
                        item["scraped_data"], item["annotation"], item["url"],
                    )
                    item["saved"] = True
            st.rerun()
    with bc2:
        if st.button("🗑️ 清空审核台", use_container_width=True, key="batch_clear"):
            st.session_state.batch_items = []
            st.rerun()

    # Show ingest feedback for last saved item
    if st.session_state.get("ingest_result"):
        ir = st.session_state.ingest_result
        if ir.get("action") == "case_generated":
            st.success(f"知识库已更新: {ir.get('case_file', '')}")
        elif ir.get("action") == "error":
            st.error(f"入库失败: {ir.get('_ingest_error', '未知错误')}")
        elif ir.get("action") == "skipped":
            st.info(f"已跳过: {ir.get('case_file', 'URL已存在')}")



def _render_entry_result_preview(prefix: str):
    """Render annotation result as Figma-style result cards."""
    ann = st.session_state.get("annotation_result")
    if not ann:
        return
    source = st.session_state.get("_result_source", "")
    scraped = st.session_state.get("scraped_data") or {}
    url = scraped.get("原文链接", "")
    platform = scraped.get("来源平台", ann.get("来源平台", "未知"))
    sev = ann.get("严重度评级", "P2")
    sev_colors = {"P0": "#dc2626", "P1": "#ea580c", "P2": "#ca8a04", "P3": "#16a34a"}
    sev_color = sev_colors.get(sev, "#64748B")
    sev_bg = {"P0": "#fde8e8", "P1": "#fef0e6", "P2": "#fef9c3", "P3": "#dcfce7"}.get(sev, "#f8fafc")
    title = (scraped.get("原文内容", "") or ann.get("摘要", "") or url)[:60]
    summary = ann.get("摘要", scraped.get("原文内容", ""))[:200]
    sentiment = ann.get("情感分析", {}).get("整体情感", "")
    action = ann.get("分流建议", "")
    interaction = ""
    social = scraped.get("社媒数据") or {}
    if social:
        likes = social.get("点赞", 0) or 0
        comments = social.get("评论", 0) or 0
        if likes or comments:
            interaction = f"📊 互动 {likes + comments}"
    st.markdown(
        f'<div class="card"><div class="card-title">📋 标注结果预览</div>'
        f'<div class="result-card" style="border-left-color:{sev_color};">'
        f'<div class="r-header">'
        f'<span class="r-title">{html.escape(title)} · {html.escape(platform)}</span>'
        f'<span class="r-tag" style="background:{sev_bg};color:{sev_color};">{html.escape(sev)}</span>'
        f'</div>'
        f'<div class="r-body">{html.escape(summary)}</div>'
        f'<div class="r-info">'
        f'<span>📅 {html.escape(scraped.get("发布时间", "") or "—")}</span>'
        f'<span>👤 {html.escape((social.get("作者") or "")[:20] or "—")}</span>'
        f'{f"<span>{html.escape(interaction)}</span>" if interaction else ""}'
        f'<span>🏷️ {html.escape(action)}</span>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )


def render_tab_entry():
    """Render the merged 录入研判 tab matching Figma HTML design."""

    # ── Batch auto-process ──
    if st.session_state.get("batch_auto_process"):
        queue = list(st.session_state.get("entry_queue", []))
        st.session_state.batch_auto_process = False
        st.session_state.batch_items = []
        if not queue:
            st.warning("队列为空，无法批量处理")
        else:
            total = len(queue)
            progress_bar = st.progress(0)
            status_text = st.empty()
            for idx, url in enumerate(queue):
                status_text.text(f"正在处理 {idx + 1}/{total}: {url[:80]}...")
                progress_bar.progress((idx + 1) / total)
                platform = "未知"
                try:
                    from engine.scraper import _detect_platform
                    platform = _detect_platform(url) if url else "未知"
                except Exception:
                    pass
                item = {"url": url, "title": "", "platform": platform, "status": "pending", "scraped_data": None, "annotation": None, "error": None, "saved": False}
                try:
                    from engine.scraper import scrape
                    data = scrape(url)
                    if data and data.get("_scrape_error"):
                        raise Exception(data["_scrape_error"])
                    item["scraped_data"] = data
                    item["title"] = (data.get("原文内容", "") or "")[:100].replace("\n", " ")
                    item["platform"] = data.get("来源平台", platform)
                    config = st.session_state.config
                    if config and config.get("api_key"):
                        system_prompt = st.session_state.get("_cached_sys_prompt", "")
                        if not system_prompt:
                            from engine.annotate import build_system_prompt
                            system_prompt, _ = build_system_prompt(data.get("原文内容", ""))
                        from engine.annotate import format_user_message, annotate_one_stream
                        user_msg = format_user_message(data)
                        result = None
                        for event in annotate_one_stream(user_msg, system_prompt, config):
                            if event["type"] == "result":
                                result = event["data"]
                        if result and not result.get("error"):
                            item["annotation"] = result
                            item["status"] = "success"
                        else:
                            item["status"] = "failed"
                            item["error"] = (result or {}).get("message", "标注失败")
                    else:
                        item["status"] = "failed"
                        item["error"] = "未配置 API Key"
                except Exception as e:
                    item["status"] = "failed"
                    item["error"] = str(e)[:200]
                st.session_state.batch_items.append(item)
            progress_bar.empty()
            status_text.empty()

    if st.session_state.get("batch_items"):
        _render_batch_review()
        st.divider()
        st.caption("或继续单条录入:")

    # ── Queue ──
    entry_queue = st.session_state.get("entry_queue", [])
    queue_fill_url = ""
    if entry_queue:
        if st.session_state.get(f"{TAB_KEY}_queue_done"):
            if entry_queue:
                entry_queue.pop(0)
                st.session_state.entry_queue = entry_queue
            st.session_state[f"{TAB_KEY}_queue_done"] = False
        if entry_queue:
            queue_fill_url = entry_queue[0]

    # ── Fill values ──
    fill_values = st.session_state.pop(f"{TAB_KEY}fill_values", None) or {}
    if fill_values:
        for f in ["author", "likes", "comments_count", "followers", "views", "country", "publish_time", "homepage", "platform", "severity", "action", "sentiment", "categories", "summary", "reason"]:
            st.session_state.pop(f"{TAB_KEY}{f}", None)
        for f, val in fill_values.items():
            st.session_state[f"{TAB_KEY}{f}"] = val

    # ═══ DUAL COLUMN LAYOUT ═══
    main_col, side_col = st.columns([3, 1])

    with main_col:
        # Page header — matching Figma
        st.markdown(
            '<div class="page-header">'
            '<div><h1>录入研判</h1>'
            '<div class="subtitle">手动录入案例并进行 AI 智能研判标注</div></div>'
            '<button class="btn-outline-figma">📥 批量导入</button>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Card 1: URL Input ──
        st.markdown(
            '<div class="card"><div class="card-title">🔗 案例 URL 录入</div>',
            unsafe_allow_html=True,
        )
        u1, u2 = st.columns([4, 1])
        with u1:
            last_auto = st.session_state.get(f"{TAB_KEY}_queue_last_auto", "")
            if queue_fill_url and last_auto != queue_fill_url:
                st.session_state[f"{TAB_KEY}url_input"] = queue_fill_url
                st.session_state[f"{TAB_KEY}_queue_last_auto"] = queue_fill_url
            elif not queue_fill_url and last_auto:
                st.session_state[f"{TAB_KEY}_queue_last_auto"] = ""
            url_input = st.text_input(
                "", placeholder="请输入舆情原文链接，例如 https://weibo.com/xxx...",
                label_visibility="collapsed", key=f"{TAB_KEY}url_input",
            )
        with u2:
            try:
                from engine.scraper import _detect_platform
                pd_ = _detect_platform(url_input.strip()) if url_input.strip() else ""
            except Exception:
                pd_ = ""
            scrape_btn = st.button(
                "🔍 抓取数据", type="primary", use_container_width=True,
                disabled=not (url_input.strip() and pd_), key=f"{TAB_KEY}scrape_btn",
            )
            if pd_:
                pm = {"YouTube": "YTB", "小红书": "小红书", "抖音": "DY", "B站": "B站", "微博": "微博"}
                st.caption(f"检测到: {pm.get(pd_, pd_)}")
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Card 2: Social Media Data ──
        st.markdown(
            '<div class="card"><div class="card-title">📊 社媒数据</div>',
            unsafe_allow_html=True,
        )
        sd1, sd2, sd3, sd4, sd5 = st.columns(5)
        with sd1:
            author = st.text_input("作者", key=f"{TAB_KEY}author", value=fill_values.get("author", ""), placeholder="@用户名")
        with sd2:
            likes = st.text_input("点赞", placeholder="0", key=f"{TAB_KEY}likes", value=fill_values.get("likes", ""))
        with sd3:
            comments_count = st.text_input("评论", placeholder="0", key=f"{TAB_KEY}comments_count", value=fill_values.get("comments_count", ""))
        with sd4:
            followers = st.text_input("粉丝", placeholder="0", key=f"{TAB_KEY}followers", value=fill_values.get("followers", ""))
        with sd5:
            views = st.text_input("播放量", placeholder="0", key=f"{TAB_KEY}views", value=fill_values.get("views", ""))
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Card 3: Classification ──
        st.markdown(
            '<div class="card"><div class="card-title">🏷️ 分类标注</div>'
            '<div class="classify-grid">',
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown('<div class="classify-item"><div class="lbl">来源平台</div>', unsafe_allow_html=True)
            platform_manual = st.selectbox("", ["微博", "小红书", "抖音", "B站", "公众号", "YouTube", "新闻媒体", "其他"], label_visibility="collapsed", key=f"{TAB_KEY}platform")
            st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="classify-item"><div class="lbl">严重度</div>', unsafe_allow_html=True)
            severity = st.selectbox("", ["P0", "P1", "P2", "P3"], label_visibility="collapsed", key=f"{TAB_KEY}severity")
            st.markdown('</div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="classify-item"><div class="lbl">分流建议</div>', unsafe_allow_html=True)
            action = st.selectbox("", ["立即处理", "持续观察", "可忽略", "正面可利用"], label_visibility="collapsed", key=f"{TAB_KEY}action")
            st.markdown('</div>', unsafe_allow_html=True)
        with c4:
            st.markdown('<div class="classify-item"><div class="lbl">情感分析</div>', unsafe_allow_html=True)
            sentiment = st.selectbox("", ["正面", "负面", "中性", "混合"], label_visibility="collapsed", key=f"{TAB_KEY}sentiment")
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)  # close classify-grid

        st.markdown('<div class="section-label">📝 摘要</div>', unsafe_allow_html=True)
        summary = st.text_area(
            "", placeholder="请输入或由 AI 自动生成该舆情案例的摘要内容...",
            height=100, label_visibility="collapsed", key=f"{TAB_KEY}summary",
        )

        # Action bar
        ab1, ab2, ab3 = st.columns([1, 1, 1])
        with ab1:
            uploaded_file = st.file_uploader("📎 上传 TXT", type=["txt"], key=f"{TAB_KEY}upload", label_visibility="collapsed")
        with ab2:
            can_save = bool((url_input.strip() and summary.strip()))
            if st.button("💾 保存案例", type="primary", use_container_width=True, disabled=not can_save, key=f"{TAB_KEY}save"):
                social_data = None
                if any([author, country := fill_values.get("country", ""), likes, comments_count, followers, views, (hp := fill_values.get("homepage", "") or "")]):
                    social_data = {"作者": author or "未知", "国家": fill_values.get("country", ""), "点赞": int(likes) if likes.isdigit() else 0, "评论": int(comments_count) if comments_count.isdigit() else 0, "粉丝": int(followers) if followers.isdigit() else 0, "播放量": int(views) if views.isdigit() else None, "时长": "", "作者主页": [fill_values.get("homepage", "")] if fill_values.get("homepage") else []}
                scraped = {"原文内容": summary.strip(), "来源平台": platform_manual, "发布者类型": f"用户: {author}" if author else "未知", "互动数据": "", "发布时间": fill_values.get("publish_time", ""), "原文链接": url_input.strip(), "评论列表": [], "社媒数据": social_data}
                annotation = {"严重度评级": severity, "分流建议": action, "情感分析": {"整体情感": sentiment}, "摘要": summary.strip(), "严重度理由": fill_values.get("reason", "人工录入"), "风险标签": [], "舆情分类": []}
                st.session_state.scraped_data = scraped
                st.session_state.annotation_result = annotation
                st.session_state._result_source = "entry"
                from ui.shared import _save_annotation_output, _do_ingest
                _save_annotation_output(scraped, annotation)
                st.session_state.ingest_result = _do_ingest(scraped, annotation, url_input.strip())
                st.success("已保存到知识库！")
                st.rerun()
        with ab3:
            if st.button("📋 清空表单", use_container_width=True, key=f"{TAB_KEY}clear"):
                for k in list(st.session_state.keys()):
                    if k.startswith(TAB_KEY):
                        del st.session_state[k]
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)  # close card

        # ── Result preview ──
        if st.session_state.get("annotation_result"):
            _render_entry_result_preview("entry_")

    # ── Right Sidebar (Figma matching) ──
    with side_col:
        # Stats: use session_state counters (reliable across reruns) with
        # query_stats fallback for cross-session persistence
        today_saved = st.session_state.get("_entry_today_count", 0)
        if today_saved == 0:
            # Fallback: count today's outputs for cold-start / new session
            try:
                today_str = _date.today().isoformat()
                _out_dir = _Path(__file__).resolve().parent.parent / "outputs"
                today_saved = len(list(_out_dir.glob(f"{today_str}_*_annotation.json")))
            except Exception:
                today_saved = 0
        try:
            from agents.curator import query_stats
            stats = query_stats()
            status_dist = stats.get("status_dist", {})
            completed = status_dist.get("已处理", 0)
            pending_review = status_dist.get("待跟进", 0)
            total_cases = stats.get("total_cases", 0)
            sev_dist = stats.get("severity_dist", {})
        except Exception:
            completed = 0
            pending_review = 0
            total_cases = 0
            sev_dist = {}
        st.markdown(
            f'<div class="sidebar-card">'
            f'<h3>📌 录入记录 <span class="badge blue">今日 {today_saved}</span></h3>'
            f'<ul class="sidebar-list">'
            f'<li><span>已完成</span><span class="val">{completed} 条</span></li>'
            f'<li><span>待审核</span><span class="val">{pending_review} 条</span></li>'
            f'<li><span>草稿箱</span><span class="val">0 条</span></li>'
            f'</ul></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sidebar-card">'
            '<h3>🏷️ 常用标签</h3>'
            '<div style="display:flex;gap:6px;flex-wrap:wrap;">'
            '<span class="tag active">食品安全</span>'
            '<span class="tag">产品质量</span>'
            '<span class="tag">舆情预警</span>'
            '<span class="tag">消费者权益</span>'
            '<span class="tag">行业监管</span>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        # AI 辅助 — dynamic data based on KB state
        p0p1 = sev_dist.get("P0", 0) + sev_dist.get("P1", 0)
        ai_lines = []
        if total_cases > 0:
            ai_lines.append(f'<li><span>知识库案例</span><span class="val">{total_cases} 条</span></li>')
        if p0p1 > 0:
            ai_lines.append(f'<li><span>高优 P0/P1</span><span class="val" style="color:#dc2626;">{p0p1} 条</span></li>')
        if not ai_lines:
            ai_lines.append('<li><span style="color:#64748B;">入库案例后将自动分析</span></li>')
        st.markdown(
            '<div class="sidebar-card">'
            '<h3>🤖 AI 辅助</h3>'
            f'<ul class="sidebar-list">{"".join(ai_lines)}</ul>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Queue status
        if entry_queue:
            st.markdown(
                f'<div class="sidebar-card">'
                f'<h3>📋 待处理队列</h3>'
                f'<p style="font-size:13px;color:#64748B;">{len(entry_queue)} 条待处理</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button("清空队列", key=f"{TAB_KEY}clear_queue"):
                st.session_state.entry_queue = []
                st.rerun()

    # ── Scrape handler (deferred) ──
    if 'scrape_btn' in dir() and scrape_btn and url_input.strip() and pd_:
        from ui.shared import do_scrape
        data = do_scrape(url_input.strip())
        fv = {}
        if data:
            social = data.get("社媒数据", {}) or {}
            homepage_list = social.get("作者主页", [])
            fv = {"author": social.get("作者", ""), "likes": str(social.get("点赞", "")) if social.get("点赞") is not None else "", "comments_count": str(social.get("评论", "")) if social.get("评论") is not None else "", "followers": str(social.get("粉丝", "")) if social.get("粉丝") is not None else "", "views": str(social.get("播放量", "")) if social.get("播放量") is not None else "", "country": social.get("国家", ""), "publish_time": data.get("发布时间", ""), "homepage": homepage_list[0] if homepage_list else ""}
            pm2 = {"YouTube": "YouTube", "小红书": "小红书", "抖音": "抖音", "B站": "B站", "微博": "微博"}
            raw_pf = data.get("来源平台", "")
            fv["platform"] = pm2.get(raw_pf, raw_pf or platform_manual)
            if data.get("原文内容"):
                fv["summary"] = data["原文内容"][:200].replace("\n", " ")
        if data and not data.get("_scrape_error"):
            social = data.get("社媒数据", {}) or {}
            content = data.get("原文内容", "")
            config = st.session_state.config
            if config and config.get("api_key"):
                from engine.annotate import build_system_prompt, format_user_message, annotate_one_stream
                system_prompt = build_system_prompt(content)[0]
                user_msg = format_user_message(data)
                progress = st.empty()
                result = None
                for event in annotate_one_stream(user_msg, system_prompt, config):
                    if event["type"] == "result":
                        result = event["data"]
                        progress.empty()
                st.session_state.annotation_result = result
                st.session_state._result_source = "entry"
                st.session_state.correction_result = None
                st.session_state.ingest_result = None
                from ui.shared import _clear_correction_widgets
                _clear_correction_widgets()
                if result and not result.get("error"):
                    from ui.shared import _save_annotation_output, _do_ingest
                    _save_annotation_output(data, result, url_input.strip())
                    st.session_state.ingest_result = _do_ingest(data, result, url_input.strip())
                    sev = result.get("严重度评级", "P2")
                    if sev in ("P0", "P1", "P2", "P3"):
                        fv["severity"] = sev
                    act = result.get("分流建议", "持续观察")
                    if act in ("立即处理", "持续观察", "可忽略", "正面可利用"):
                        fv["action"] = act
                    sent = result.get("情感分析", {}).get("整体情感", "中性")
                    if sent in ("正面", "负面", "中性", "混合"):
                        fv["sentiment"] = sent
                    fv["summary"] = result.get("摘要", "") or fv.get("summary", "")
                    fv["reason"] = result.get("严重度理由", "")
                    cats = [c for c in (result.get("舆情分类", []) or []) if c in CATEGORY_OPTIONS]
                    if cats:
                        fv["categories"] = cats
        if data and data.get("_scrape_error"):
            st.error(f"抓取失败: {data['_scrape_error']}")
        if fv:
            st.session_state[f"{TAB_KEY}fill_values"] = fv
        st.rerun()

    # Ingest feedback
    if st.session_state.get("ingest_result"):
        ir = st.session_state.ingest_result
        if ir["action"] == "case_generated":
            st.success(f"知识库已更新: {ir['case_file']}")
            queue = st.session_state.get("entry_queue", [])
            if queue:
                st.session_state[f"{TAB_KEY}_queue_done"] = True
                import time
                time.sleep(2)
                st.rerun()
        elif ir["action"] in ("already_exists", "skipped"):
            st.info(f"已跳过: {ir.get('case_file', ir.get('message', ''))}")
            queue = st.session_state.get("entry_queue", [])
            if queue:
                st.session_state[f"{TAB_KEY}_queue_done"] = True
                st.rerun()
        elif ir["action"] == "error":
            st.error(f"入库失败: {ir.get('_ingest_error', '未知错误')}")

