# -*- coding: utf-8 -*-
"""Tab 2: URL scraping — paste YouTube/小红书 links, scrape + annotate.

Extracted from app.py — no logic changes, pure code movement.
"""

import streamlit as st
from engine.annotate import (
    annotate_one_stream,
    build_system_prompt,
    format_user_message,
)
from engine.scraper import _detect_platform, scrape
from ui.shared import (
    _clear_correction_widgets,
    _do_ingest,
    _render_annotation_result,
    _save_annotation_output,
    do_scrape,
)


def render_tab2(_pending_annotate_url, _pending_batch_urls):
    """Render the URL scraping tab (Tab 2)."""

    st.info("URL 抓取需要本地浏览器环境，在线 Demo 不可用。支持 YouTube、小红书和抖音链接。")
    url_input = st.text_input(
        "粘贴舆情链接",
        placeholder="https://www.xiaohongshu.com/explore/... 或 https://www.youtube.com/watch?v=... 或 https://www.douyin.com/video/...",
        key="url_input",
    )
    # URL validation
    url_valid = True
    url_platform = ""
    if url_input.strip():
        url_platform = _detect_platform(url_input.strip())
        if url_platform not in ("YouTube", "小红书", "抖音"):
            url_valid = False
            st.warning(f"暂不支持「{url_platform}」平台。目前仅支持 YouTube、小红书和抖音链接。")

    col1, col2 = st.columns([1, 1])
    with col1:
        scrape_btn = st.button("抓取内容", type="primary", use_container_width=True,
                               disabled=not (url_input.strip() and url_valid))
    with col2:
        annotate_scraped_btn = st.button("抓取并标注", type="secondary", use_container_width=True,
                                         disabled=not (url_input.strip() and url_valid))

    # Deferred URL annotation (old result cleared, now run actual scrape+annotate)
    if _pending_annotate_url:
        data = do_scrape(_pending_annotate_url)
        if data and not data.get("_scrape_error"):
            config = st.session_state.config
            system_prompt = build_system_prompt(data.get("原文内容", ""))[0]
            user_msg = format_user_message(data)
            progress = st.empty()
            result = None
            for event in annotate_one_stream(user_msg, system_prompt, config):
                if event["type"] == "progress":
                    progress.info(f"AI 正在分析... (已生成 {event['chars']} 字符)")
                elif event["type"] == "result":
                    result = event["data"]
                    progress.empty()
            if result is None:
                result = {"error": True, "message": "流式标注未返回结果"}
            st.session_state.annotation_result = result
            st.session_state._result_source = "url"
            st.session_state.correction_result = None
            st.session_state.ingest_result = None
            _clear_correction_widgets()
            if result and not result.get("error"):
                _save_annotation_output(data, result, _pending_annotate_url)
                st.session_state.ingest_result = _do_ingest(data, result, _pending_annotate_url)
            st.session_state._needs_rerun = True

    # --- Batch mode ---
    st.divider()
    batch_btn = False
    batch_urls_text = ""
    batch_mode = st.checkbox("📦 批量模式", value=False, key="batch_mode_checkbox",
                             help="粘贴多个URL（每行一个），批量抓取+标注")
    if batch_mode:
        batch_urls_text = st.text_area(
            "粘贴多个URL（每行一个）",
            placeholder="https://www.youtube.com/watch?v=xxx\nhttps://www.xiaohongshu.com/explore/xxx\nhttps://www.reddit.com/r/...",
            height=120,
            key="batch_urls_text",
        )
        urls = [u.strip() for u in batch_urls_text.split("\n") if u.strip()]
        batch_btn = st.button("批量抓取并标注", type="primary", use_container_width=True,
                              disabled=len(urls) < 2,
                              key="batch_annotate_btn")

        # Deferred batch processing
        if _pending_batch_urls:
            config = st.session_state.config
            system_prompt = build_system_prompt()[0]
            results = []
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            for i, url in enumerate(_pending_batch_urls):
                status_placeholder.info(f"🔵 正在处理 {i+1}/{len(_pending_batch_urls)}: {url[:60]}...")
                try:
                    data = scrape(url)
                    if data and not data.get("_scrape_error"):
                        user_msg = format_user_message(data)
                        result = None
                        for event in annotate_one_stream(user_msg, system_prompt, config):
                            if event["type"] == "result":
                                result = event["data"]
                        if result and not result.get("error"):
                            _save_annotation_output(data, result, url)
                            ir = _do_ingest(data, result, url)
                            results.append({
                                "url": url,
                                "platform": data.get("来源平台", "?"),
                                "severity": result.get("严重度评级", "?"),
                                "action": result.get("分流建议", "?"),
                                "summary": result.get("摘要", "")[:60],
                                "ingest": ir.get("action", "?"),
                                "error": None,
                            })
                        else:
                            results.append({"url": url, "error": result.get("message", "标注失败") if result else "无结果"})
                    else:
                        results.append({"url": url, "error": data.get("_scrape_error", "抓取失败") if data else "无数据"})
                except Exception as e:
                    results.append({"url": url, "error": str(e)})
                progress_bar.progress((i + 1) / len(_pending_batch_urls))
            status_placeholder.empty()
            progress_bar.empty()
            st.session_state.batch_results = results
            if results and not results[-1].get("error"):
                st.session_state.annotation_result = {"_batch_summary": True}
            st.session_state._needs_rerun = True

        # Batch results summary
        if st.session_state.batch_results:
            br = st.session_state.batch_results
            ok = sum(1 for r in br if not r.get("error"))
            fail = len(br) - ok
            st.divider()
            st.subheader(f"📊 批量结果: {ok}/{len(br)} 成功" + (f", {fail} 失败" if fail else ""))
            rows = []
            for j, r in enumerate(br):
                if r.get("error"):
                    rows.append(f"| {j+1} | {r['url'][:50]}... | ❌ | — | — | {r['error'][:40]} |")
                else:
                    rows.append(
                        f"| {j+1} | [{r['platform']}] {r['summary'][:40]}... "
                        f"| {r['severity']} | {r['action']} | {r['ingest']} |"
                    )
            st.markdown("| # | 内容 | 严重度 | 分流 | Ingest |\n|---|------|--------|------|--------|\n" + "\n".join(rows))

    _render_annotation_result("tab2_")

    # ═══════════════════════════════════════════════════════════════════════════════
    # Button handlers (moved from bottom of app.py into Tab 2 for locality)
    # ═══════════════════════════════════════════════════════════════════════════════

    if scrape_btn and url_input.strip():
        do_scrape(url_input.strip())

    if annotate_scraped_btn and url_input.strip():
        st.session_state.annotation_result = None
        st.session_state.ingest_result = None
        st.session_state.correction_result = None
        st.session_state._annotate_url = url_input.strip()
        st.rerun()

    # Batch button handler
    if batch_btn and batch_urls_text.strip():
        urls = [u.strip() for u in batch_urls_text.split("\n") if u.strip()]
        if len(urls) >= 2:
            st.session_state.annotation_result = None
            st.session_state.ingest_result = None
            st.session_state.correction_result = None
            st.session_state.batch_results = None
            st.session_state._batch_urls = urls
            st.rerun()
