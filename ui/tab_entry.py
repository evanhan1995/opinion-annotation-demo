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


def render_tab_entry():
    """Render the merged 录入研判 tab."""
    st.caption("粘贴舆情链接自动抓取标注，或手动填写。支持 YouTube、小红书、抖音。")

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
        url_input = st.text_input(
            "原文链接",
            placeholder="https://www.youtube.com/watch?v=... 或小红书/抖音链接",
            key=f"{TAB_KEY}url_input",
        )
    with url_col2:
        platform_detected = ""
        if url_input.strip():
            platform_detected = _detect_platform(url_input.strip())
            platform_label = {"YouTube": "YTB", "小红书": "小红书", "抖音": "DY"}.get(
                platform_detected, platform_detected or "..."
            )
            st.caption(f"检测到: {platform_label}")
    with url_col3:
        scrape_btn = st.button(
            "🔍 抓取标注", type="primary", use_container_width=True,
            disabled=not (url_input.strip() and platform_detected in ("YouTube", "小红书", "抖音")),
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
    platform_options = ["小红书", "YouTube", "Instagram", "TikTok", "X (Twitter)", "Reddit", "新闻媒体", "论坛", "其他"]
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
            pf_map = {"YouTube": "YouTube", "小红书": "小红书", "抖音": "TikTok",
                       "xiaohongshu": "小红书", "douyin": "抖音", "youtube": "YouTube"}
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
