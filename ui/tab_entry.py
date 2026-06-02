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

                    cats = ann.get("舆情分类", []) or []
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


def render_tab_entry():
    """Render the merged 录入研判 tab."""
    st.caption("粘贴舆情链接自动抓取标注，或手动填写。支持 YouTube、小红书、抖音。")

    # ── Batch auto-process: Monitor → 批量研判 ────────────────────────────
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

                platform = _detect_platform(url) if url else "未知"
                item = {
                    "url": url,
                    "title": "",
                    "platform": platform,
                    "status": "pending",
                    "scraped_data": None,
                    "annotation": None,
                    "error": None,
                    "saved": False,
                }

                try:
                    # Scrape
                    data = scrape(url)
                    if data and data.get("_scrape_error"):
                        raise Exception(data["_scrape_error"])

                    item["scraped_data"] = data
                    item["title"] = (data.get("原文内容", "") or "")[:100].replace("\n", " ")
                    item["platform"] = data.get("来源平台", platform)

                    # Annotate
                    config = st.session_state.config
                    if config and config.get("api_key"):
                        system_prompt = build_system_prompt(data.get("原文内容", ""))[0]
                        user_msg = format_user_message(data)
                        result = None
                        for event in annotate_one_stream(user_msg, system_prompt, config):
                            if event["type"] == "result":
                                result = event["data"]
                        if result is None:
                            result = {"error": True, "message": "流式标注未返回结果"}

                        if result and not result.get("error"):
                            item["annotation"] = result
                            item["status"] = "success"
                            _save_annotation_output(data, result, url)
                        else:
                            item["status"] = "failed"
                            item["error"] = result.get("message", "标注失败") if result else "标注返回空"
                    else:
                        item["status"] = "failed"
                        item["error"] = "未配置 API Key"

                except Exception as e:
                    item["status"] = "failed"
                    item["error"] = str(e)[:200]

                st.session_state.batch_items.append(item)

            progress_bar.empty()
            status_text.empty()

            success_n = sum(1 for it in st.session_state.batch_items if it["status"] == "success")
            failed_n = sum(1 for it in st.session_state.batch_items if it["status"] == "failed")
            if failed_n:
                st.warning(f"批量处理完成: {success_n} 成功, {failed_n} 失败")
            else:
                st.success(f"批量处理完成: {success_n} 条全部成功")

    # ── Batch review mode ──────────────────────────────────────────────────
    if st.session_state.get("batch_items"):
        _render_batch_review()
        st.divider()
        st.caption("或继续单条录入:")

    # ── Queue mode: Monitor → 录入研判 bridge ────────────────────────────
    entry_queue = st.session_state.get("entry_queue", [])
    queue_fill_url = ""
    if entry_queue:
        # Advance queue: pop completed item after successful ingest
        if st.session_state.get(f"{TAB_KEY}_queue_done"):
            if entry_queue:
                entry_queue.pop(0)
                st.session_state.entry_queue = entry_queue
            st.session_state[f"{TAB_KEY}_queue_done"] = False

        if entry_queue:
            queue_fill_url = entry_queue[0]
            st.divider()
            qc1, qc2, qc3 = st.columns([2, 1, 1])
            with qc1:
                remaining = len(entry_queue)
                st.info(f"📋 待处理队列: {remaining} 条（来自 Monitor 导入）")
            with qc2:
                if st.button("清空队列", key=f"{TAB_KEY}clear_queue"):
                    st.session_state.entry_queue = []
                    st.rerun()
            with qc3:
                url_preview = queue_fill_url[:60] + "..." if len(queue_fill_url) > 60 else queue_fill_url
                st.caption(f"当前: {url_preview}")

    # ── Consume pending fill values from scrape button ────────────────
    fill_values = st.session_state.pop(f"{TAB_KEY}fill_values", None) or {}
    if fill_values:
        for f in ["author", "likes", "comments_count", "followers", "views",
                   "country", "publish_time", "homepage", "platform",
                   "severity", "action", "sentiment", "categories",
                   "summary", "reason"]:
            st.session_state.pop(f"{TAB_KEY}{f}", None)
        # Write values directly into session_state so widgets pick them up natively
        for f, val in fill_values.items():
            st.session_state[f"{TAB_KEY}{f}"] = val

    # ── Row 1: URL input + platform + action ──────────────────────────
    url_col1, url_col2, url_col3 = st.columns([3, 1, 1])
    with url_col1:
        # Auto-fill from queue when queue advances (only on URL change)
        last_auto = st.session_state.get(f"{TAB_KEY}_queue_last_auto", "")
        if queue_fill_url and last_auto != queue_fill_url:
            st.session_state[f"{TAB_KEY}url_input"] = queue_fill_url
            st.session_state[f"{TAB_KEY}_queue_last_auto"] = queue_fill_url
        elif not queue_fill_url and last_auto:
            st.session_state[f"{TAB_KEY}_queue_last_auto"] = ""

        url_input = st.text_input(
            "原文链接",
            placeholder="https://www.youtube.com/watch?v=... 或小红书/抖音链接",
            key=f"{TAB_KEY}url_input",
        )
    with url_col2:
        platform_detected = ""
        if url_input.strip():
            platform_detected = _detect_platform(url_input.strip())
            platform_label = {"YouTube": "YTB", "小红书": "小红书", "抖音": "DY",
                             "B站": "B站", "微博": "微博"}.get(
                platform_detected, platform_detected or "..."
            )
            st.caption(f"检测到: {platform_label}")
    with url_col3:
        scrape_btn = st.button(
            "🔍 抓取标注", type="primary", use_container_width=True,
            disabled=not (url_input.strip() and platform_detected in ("YouTube", "小红书", "抖音", "B站", "微博")),
            key=f"{TAB_KEY}scrape_btn",
        )

    # ── Row 2: TXT upload + AI summary ───────────────────────────────
    st.divider()
    txt_col1, txt_col2 = st.columns([2, 1])
    with txt_col1:
        uploaded_file = st.file_uploader(
            "📎 上传 TXT 文件（AI 自动总结）", type=["txt"], key=f"{TAB_KEY}upload"
        )
    with txt_col2:
        spacer()  # spacer
        if st.button("🤖 AI 总结", disabled=not bool(uploaded_file), key=f"{TAB_KEY}ai_summary",
                     use_container_width=True, help="读取上传的 txt 内容，AI 生成简介摘要"):
            try:
                txt_content = uploaded_file.read().decode("utf-8")
                st.session_state[f"{TAB_KEY}txt_content"] = txt_content[:5000]
                config = st.session_state.config
                if config and config.get("api_key"):
                    from openai import OpenAI
                    client = OpenAI(api_key=config["api_key"], base_url=config["api_base"])
                    resp = client.chat.completions.create(
                        model=config["model"], max_tokens=200, temperature=0.3, timeout=30,
                        messages=[{"role": "user", "content": f"请用80字以内总结以下内容的核心问题、涉及品牌/产品、舆论倾向：\n\n{txt_content[:3000]}"}],
                    )
                    st.session_state[f"{TAB_KEY}ai_result"] = resp.choices[0].message.content.strip()
                    st.success("AI 总结已生成")
                else:
                    st.warning("请先在侧边栏加载知识库（配置 API Key）")
            except Exception as e:
                st.error(f"上传失败: {e}")

    # ── Row 3: Social media data (always visible) ─────────────────────
    st.divider()
    st.caption("📊 社媒数据")

    sd1, sd2, sd3, sd4 = st.columns(4)
    with sd1:
        author = st.text_input("作者名称", key=f"{TAB_KEY}author",
                               value=fill_values.get("author", ""))
    with sd2:
        likes = st.text_input("点赞数", placeholder="0", key=f"{TAB_KEY}likes",
                              value=fill_values.get("likes", ""))
    with sd3:
        comments_count = st.text_input("评论数", placeholder="0", key=f"{TAB_KEY}comments_count",
                                       value=fill_values.get("comments_count", ""))
    with sd4:
        followers = st.text_input("粉丝数", placeholder="0", key=f"{TAB_KEY}followers",
                                  value=fill_values.get("followers", ""))

    sd5, sd6, sd7 = st.columns(3)
    with sd5:
        views = st.text_input("播放量", placeholder="0", key=f"{TAB_KEY}views",
                              value=fill_values.get("views", ""))
    with sd6:
        country = st.text_input("国家", placeholder="CN/US/...", key=f"{TAB_KEY}country",
                                value=fill_values.get("country", ""))
    with sd7:
        publish_time = st.text_input("发布时间", placeholder="2025-01-15", key=f"{TAB_KEY}publish_time",
                                     value=fill_values.get("publish_time", ""))

    homepage = st.text_input("作者主页 URL", placeholder="https://...", key=f"{TAB_KEY}homepage",
                             value=fill_values.get("homepage", ""))

    # ── Row 4: Classification & rating ────────────────────────────────
    st.divider()
    platform_options = ["小红书", "YouTube", "Instagram", "TikTok", "X (Twitter)", "Reddit",
                       "B站", "微博", "新闻媒体", "论坛", "其他"]
    pf_val = fill_values.get("platform", "")
    platform_index = platform_options.index(pf_val) if pf_val in platform_options else 0
    platform_manual = st.selectbox(
        "来源平台（手动选择）",
        platform_options,
        key=f"{TAB_KEY}platform",
        index=platform_index,
    )

    severity_options = ["P0", "P1", "P2", "P3"]
    action_options = ["立即处理", "持续观察", "可忽略", "正面可利用"]
    sentiment_options = ["正面", "负面", "中性", "混合"]

    d1, d2 = st.columns(2)
    with d1:
        sev_val = fill_values.get("severity", "")
        sev_index = severity_options.index(sev_val) if sev_val in severity_options else 2
        severity = st.selectbox(
            "严重度评级", severity_options,
            key=f"{TAB_KEY}severity", index=sev_index,
        )
        categories = st.multiselect("舆情分类", CATEGORY_OPTIONS, key=f"{TAB_KEY}categories",
                                    default=fill_values.get("categories", None))
    with d2:
        act_val = fill_values.get("action", "")
        act_index = action_options.index(act_val) if act_val in action_options else 1
        action = st.selectbox(
            "分流建议", action_options,
            key=f"{TAB_KEY}action", index=act_index,
        )
        sent_val = fill_values.get("sentiment", "")
        sent_index = sentiment_options.index(sent_val) if sent_val in sentiment_options else 2
        sentiment = st.selectbox(
            "整体情感", sentiment_options,
            key=f"{TAB_KEY}sentiment", index=sent_index,
        )

    # ── Row 5: Summary & reason ───────────────────────────────────────
    ai_text = st.session_state.get(f"{TAB_KEY}ai_result", "")
    summary_default = fill_values.get("summary") or ai_text or st.session_state.get(f"{TAB_KEY}summary_default", "")
    summary = st.text_area(
        "简介 *", placeholder="案例摘要（必填。可用 AI 总结自动填充）",
        height=120, key=f"{TAB_KEY}summary", value=summary_default,
    )
    reason = st.text_input(
        "严重度理由", placeholder="为什么评定这个严重度...", key=f"{TAB_KEY}reason",
        value=fill_values.get("reason", ""),
    )

    # ── Row 6: Save buttons ───────────────────────────────────────────
    sc1, sc2 = st.columns([2, 1])
    with sc1:
        can_save = bool((url_input.strip() and summary.strip()))
        if st.button("💾 保存到知识库", type="primary", use_container_width=True,
                     disabled=not can_save, key=f"{TAB_KEY}save"):
            social_data = None
            if any([author, country, likes, comments_count, followers, views, homepage.strip()]):
                social_data = {
                    "作者": author or "未知",
                    "国家": country,
                    "点赞": int(likes) if likes.isdigit() else 0,
                    "评论": int(comments_count) if comments_count.isdigit() else 0,
                    "粉丝": int(followers) if followers.isdigit() else 0,
                    "播放量": int(views) if views.isdigit() else None,
                    "时长": "",
                    "作者主页": [homepage] if homepage.strip() else [],
                }

            scraped = {
                "原文内容": summary.strip(),
                "来源平台": platform_manual,
                "发布者类型": f"用户: {author}" if author else "未知",
                "互动数据": "",
                "发布时间": publish_time or "",
                "原文链接": url_input.strip(),
                "评论列表": [],
                "社媒数据": social_data,
            }
            annotation = {
                "严重度评级": severity,
                "分流建议": action,
                "情感分析": {"整体情感": sentiment},
                "摘要": summary.strip(),
                "严重度理由": reason or "人工录入",
                "风险标签": [],
                "舆情分类": categories,
            }
            st.session_state.scraped_data = scraped
            st.session_state.annotation_result = annotation
            st.session_state._result_source = "entry"
            _save_annotation_output(scraped, annotation)
            st.session_state.ingest_result = _do_ingest(scraped, annotation, url_input.strip())
            st.success("已保存到知识库！")
            st.session_state._needs_rerun = True

    with sc2:
        if st.button("📋 清空表单", use_container_width=True, key=f"{TAB_KEY}clear",
                     help="清空所有字段，准备录入下一条"):
            for k in list(st.session_state.keys()):
                if k.startswith(TAB_KEY):
                    del st.session_state[k]
            st.rerun()

    # ── Row 7: Annotation result ──────────────────────────────────────
    _render_annotation_result("entry_", show_social_card=False)

    # ── Scrape button handler (deferred execution) ────────────────────
    if scrape_btn and url_input.strip():
        data = do_scrape(url_input.strip())

        # Always extract social data for auto-fill (even on partial/failed scrape)
        fv = {}
        if data:
            social = data.get("社媒数据", {}) or {}
            homepage_list = social.get("作者主页", [])
            content = data.get("原文内容", "")

            fv = {
                "author": social.get("作者", ""),
                "likes": str(social.get("点赞", "")) if social.get("点赞") is not None else "",
                "comments_count": str(social.get("评论", "")) if social.get("评论") is not None else "",
                "followers": str(social.get("粉丝", "")) if social.get("粉丝") is not None else "",
                "views": str(social.get("播放量", "")) if social.get("播放量") is not None else "",
                "country": social.get("国家", ""),
                "publish_time": data.get("发布时间", ""),
                "homepage": homepage_list[0] if homepage_list else "",
            }

            # Auto-detect platform
            pf_map = {"YouTube": "YouTube", "小红书": "小红书", "抖音": "抖音",
                       "B站": "B站", "微博": "微博",
                       "xiaohongshu": "小红书", "douyin": "抖音", "youtube": "YouTube",
                       "bilibili": "B站", "weibo": "微博"}
            raw_pf = data.get("来源平台", "")
            fv["platform"] = pf_map.get(raw_pf, raw_pf or platform_manual)

            # Auto-fill summary snippet
            if content:
                fv["summary"] = content[:200].replace("\n", " ")

        if data and not data.get("_scrape_error"):
            social = data.get("社媒数据", {}) or {}
            content = data.get("原文内容", "")

            # Run AI annotation
            config = st.session_state.config
            if config and config.get("api_key"):
                system_prompt = build_system_prompt(content)[0]
                user_msg = format_user_message(data)
                progress = st.empty()
                result = None
                for event in annotate_one_stream(user_msg, system_prompt, config):
                    if event["type"] == "result":
                        result = event["data"]
                        progress.empty()
                if result is None:
                    result = {"error": True, "message": "流式标注未返回结果"}
                st.session_state.annotation_result = result
                st.session_state._result_source = "entry"
                st.session_state.correction_result = None
                st.session_state.ingest_result = None
                _clear_correction_widgets()
                if result and not result.get("error"):
                    _save_annotation_output(data, result, url_input.strip())
                    st.session_state.ingest_result = _do_ingest(data, result, url_input.strip())
                    # Fill annotation fields into staging dict
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
                    cats = result.get("舆情分类", [])
                    if isinstance(cats, list):
                        fv["categories"] = cats

        if data and data.get("_scrape_error"):
            st.error(f"抓取失败: {data['_scrape_error']}")

        # Stage fill values for next render (always, even on partial failure)
        if fv:
            st.session_state[f"{TAB_KEY}fill_values"] = fv
        st.rerun()

    # Ingest result feedback
    if st.session_state.ingest_result:
        ir = st.session_state.ingest_result
        if ir["action"] == "case_generated":
            st.success(f"知识库已更新: {ir['case_file']}")
            # If processing from queue, mark current item done
            queue = st.session_state.get("entry_queue", [])
            if queue:
                st.session_state[f"{TAB_KEY}_queue_done"] = True
                st.success(f"队列剩余: {len(queue) - 1} 条。3秒后自动加载下一条...")
                import time
                time.sleep(2)
                st.rerun()
        elif ir["action"] in ("already_exists", "skipped"):
            st.info(f"已跳过: {ir.get('case_file', ir.get('message', ''))}")
            queue = st.session_state.get("entry_queue", [])
            if queue:
                st.session_state[f"{TAB_KEY}_queue_done"] = True
                st.rerun()
