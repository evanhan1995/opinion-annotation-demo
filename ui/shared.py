# -*- coding: utf-8 -*-
"""Shared UI utilities for the annotation dashboard.

All render helpers, annotation helpers, and I/O functions used by tabs and sidebar.
Extracted from app.py — no logic changes, pure code movement.
"""

import json
import re
from datetime import date, datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = PROJECT_DIR / "engine"
OUTPUT_DIR = PROJECT_DIR / "outputs"

import streamlit as st
from engine.annotate import (
    build_system_prompt,
    CATEGORY_OPTIONS,
    find_annotation_history,
    diff_annotations,
    find_similar_cases,
)
from engine.correction_handler import handle_correction
from engine.ingestor import ingest
from engine.scraper import (
    PLATFORM_ABBREV,
    _extract_content_id,
    fetch_youtube_subtitles,
    scrape,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Wiki browser helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown content. Returns at minimum {title, type, _body}."""
    meta = {"title": "", "type": ""}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip()
                    if key in ("title", "type", "severity", "action", "confidence", "created", "updated"):
                        meta[key] = val
            meta["_body"] = parts[2]
    if "_body" not in meta:
        meta["_body"] = content
    return meta


def _load_wiki_pages() -> list[dict]:
    """Scan wiki/ directory and load metadata for all .md pages.

    Returns list of dicts: {path, dir, title, type, filename, content}
    Sorted: cases numerically, others alphabetically.
    """
    pages = []
    wiki_dir = PROJECT_DIR / "wiki"
    dir_order = ["concepts", "entities", "sources", "syntheses", "cases", "authors"]

    for dirname in dir_order:
        dir_path = wiki_dir / dirname
        if not dir_path.exists():
            continue
        files = sorted(dir_path.glob("*.md"))
        for f in files:
            if f.name == "index.md":
                continue
            try:
                text = f.read_text(encoding="utf-8")
                meta = _parse_frontmatter(text)
                pages.append({
                    "path": f"{dirname}/{f.name}",
                    "dir": dirname,
                    "title": meta.get("title", f.stem),
                    "type": meta.get("type", dirname),
                    "filename": f.name,
                    "content": meta.get("_body", text),
                })
            except Exception:
                continue

    return pages


def _convert_wikilinks(text: str) -> str:
    """Convert [[path|display]] wikilinks to [display](path) for Streamlit rendering."""
    def _replace_wl(m):
        target = m.group(1)
        display = m.group(2) if m.group(2) else target.split("/")[-1]
        return f"[{display}]({target})"
    return re.sub(r'\[\[([^\]|]+)(?:\|([^\]|]+))?\]\]', _replace_wl, text)


def _render_citations(citations: list):
    """Render clickable citation buttons that switch to the knowledge base tab."""
    cols = st.columns(len(citations))
    for i, c in enumerate(citations):
        with cols[i]:
            label = f"\U0001f4d6 {c['title'][:20]}"
            if st.button(label, key=f"cite_{c['path']}_{i}", use_container_width=True):
                st.session_state._selected_page = c["path"]
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# Annotation result renderer
# ═══════════════════════════════════════════════════════════════════════════════

def _render_annotation_result(key_prefix: str = ""):
    """Render annotation result display. Only called inside annotation tabs.

    key_prefix distinguishes widgets between Tab1/Tab2 to avoid duplicate key errors.
    """
    result = st.session_state.annotation_result
    if not result:
        return
    # Source filter: only render if result belongs to this tab
    source_map = {"tab1_": "manual", "tab2_": "url", "demo_": "demo"}
    expected = source_map.get(key_prefix, "")
    actual = st.session_state.get("_result_source", "")
    if expected and actual and expected != actual and not result.get("_batch_summary"):
        return

    if st.session_state.scraped_data:
        with st.expander("原始数据预览", expanded=False, key=f"{key_prefix}raw_preview_expander"):
            st.json(st.session_state.scraped_data)

    st.divider()

    if result.get("error"):
        st.error(f"标注失败: {result.get('message', '未知错误')}")
        if "raw_response" in result:
            st.text(result["raw_response"][:500])
        return

    # -------- 社媒数据卡片 --------
    scraped = st.session_state.scraped_data
    social = scraped.get("社媒数据") if scraped else None
    if social and social.get("作者"):
        platform = scraped.get("来源平台", "?")
        pub_time = scraped.get("发布时间", "") or "未知"
        with st.expander(f"\U0001f4ca 社媒数据 — {social.get('作者', '?')}", expanded=False, key=f"{key_prefix}social_card"):
            c0, c1, c2, c3, c4, c5 = st.columns(6)
            views = social.get("播放量")
            c0.metric("平台", platform)
            c1.metric("播放量", f"{views:,}" if views else "—",
                      help="[估算]" if social.get("_播放量估算") else None)
            c2.metric("点赞", f"{social.get('点赞', 0):,}" if social.get('点赞') else "—")
            c3.metric("评论", f"{social.get('评论', 0):,}" if social.get('评论') else "—")
            c4.metric("粉丝", f"{social.get('粉丝', 0):,}" if social.get('粉丝') else "—")
            c5.metric("国家", social.get("国家") or "—")
            st.caption(f"\U0001f550 发布时间: {pub_time}" + (f" | ⏱ 时长: {social.get('时长')}" if social.get('时长') else ""))
            if social.get("作者主页"):
                for hp in social["作者主页"]:
                    if hp:
                        st.caption(f"\U0001f517 {hp}")

    # -------- P0/P1 醒目告警 --------
    severity = result.get("严重度评级", "?")
    action = result.get("分流建议", "?")
    sentiment = result.get("情感分析", {}).get("整体情感", "?")

    if severity in ("P0", "P1"):
        banner_type = st.error if severity == "P0" else st.warning
        banner_type(
            f"⚠️ **{severity} 高优案例** — 分流建议: {action} | "
            f"摘要: {result.get('摘要', '')[:80]}..."
        )

    action_colors = {"立即处理": "#dc3545", "持续观察": "#ffc107", "可忽略": "#6c757d", "正面可利用": "#28a745"}

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("严重度评级", severity)
    with c2:
        st.markdown(
            f"<div style='background:{action_colors.get(action, '#6c757d')};padding:12px;border-radius:8px;text-align:center;color:white;font-weight:bold;'>{action}</div>",
            unsafe_allow_html=True,
        )
        st.caption("分流建议")
    with c3:
        st.metric("整体情感", sentiment)
    with c4:
        confidence = result.get("置信度", {}).get("整体置信度", "?")
        st.metric("置信度", confidence)

    # -------- 摘要和理由 --------
    st.markdown(f"> {result.get('摘要', '(无摘要)')}")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.caption(f"严重度理由: {result.get('严重度理由', '')}")
    with col_r2:
        st.caption(f"分流理由: {result.get('分流理由', '')}")

    # -------- 简介 --------
    summary = result.get("摘要", "")
    if summary:
        st.markdown(f"**\U0001f4dd 简介**: {summary}")

    # -------- YouTube AI 深度分析（仅 YouTube 平台）--------
    if scraped and scraped.get("来源平台") == "YouTube":
        yt_col1, yt_col2 = st.columns([1, 3])
        with yt_col1:
            if st.button("\U0001f3ac YouTube AI 视频内容分析", key=f"{key_prefix}yt_deep_analysis"):
                st.session_state[f"{key_prefix}_yt_analyze"] = True
                st.rerun()
        with yt_col2:
            if "字幕" not in scraped.get("原文内容", ""):
                if st.button("\U0001f4e5 下载字幕 TXT", key=f"{key_prefix}sub_download"):
                    st.session_state[f"{key_prefix}_fetch_sub"] = True
                    st.rerun()

        # Execute deep analysis
        if st.session_state.get(f"{key_prefix}_yt_analyze"):
            with st.spinner("正在提取字幕并深度分析视频内容..."):
                subs = fetch_youtube_subtitles(scraped.get("原文链接", ""))
                if subs:
                    config = st.session_state.config
                    system_prompt = build_system_prompt(subs)[0]
                    analysis_prompt = (
                        f"你是一个舆情分析师。请根据以下YouTube视频的标题、描述和字幕内容，"
                        f"给出深度的内容分析报告（300字以内），包括：\n"
                        f"1. 视频核心观点和立场\n2. 关键事实和数据\n3. 对品牌/产品的潜在影响\n\n"
                        f"标题：{scraped.get('原文内容', '')[:300]}\n\n字幕内容：{subs[:3000]}"
                    )
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=config["api_key"], base_url=config["api_base"])
                        resp = client.chat.completions.create(
                            model=config["model"], max_tokens=800, temperature=0.3,
                            messages=[{"role": "user", "content": analysis_prompt}],
                        )
                        deep = resp.choices[0].message.content
                        st.success("\U0001f3ac AI 视频内容分析")
                        st.markdown(deep)
                        st.session_state[f"{key_prefix}_subs_text"] = subs
                    except Exception as e:
                        st.error(f"分析失败: {e}")
                else:
                    st.warning("该视频无可抓取字幕")
            st.session_state[f"{key_prefix}_yt_analyze"] = False

        # Subtitle download
        if st.session_state.get(f"{key_prefix}_fetch_sub"):
            with st.spinner("正在下载字幕..."):
                subs = fetch_youtube_subtitles(scraped.get("原文链接", ""))
                if subs:
                    st.session_state[f"{key_prefix}_subs_text"] = subs
                    st.session_state[f"{key_prefix}_sub_ready"] = True
                else:
                    st.warning("该视频无可抓取字幕")
            st.session_state[f"{key_prefix}_fetch_sub"] = False

        if st.session_state.get(f"{key_prefix}_sub_ready"):
            subs = st.session_state.get(f"{key_prefix}_subs_text", "")
            st.download_button("⬇ 点击下载字幕文件", subs, file_name="youtube_subtitles.txt",
                              mime="text/plain", key=f"{key_prefix}_dl_btn")
        elif st.session_state.get(f"{key_prefix}_subs_text"):
            st.caption("字幕已就绪，可下载")

    # -------- 近似舆情 --------
    tags = result.get("风险标签", [])
    if tags:
        st.write(" ".join([f"`{t}`" for t in tags]))
        similar = find_similar_cases(tags, top_k=3)
        if similar:
            with st.expander(f"\U0001f50d 近似舆情 ({len(similar)} 个相似案例)", expanded=False, key=f"{key_prefix}similar_cases"):
                for s in similar:
                    cid = s["filename"].replace(".md", "")
                    st.markdown(
                        f"- [[cases/{cid}|{s['filename'].replace('.md','')}]] "
                        f"**{s['severity']}** | 命中 {s['hits']} tag | {s['title'][:50]}"
                    )
                    if st.button(f"\U0001f4d6 查看 {s['filename']}", key=f"{key_prefix}view_{s['filename']}"):
                        st.session_state._selected_page = f"cases/{s['filename']}"
                        st.rerun()

    # -------- 舆情分类 --------
    categories = result.get("舆情分类", [])
    if categories:
        cat_colors = {
            "商品问题": "#fd7e14", "商品侵权问题": "#dc3545", "售后问题": "#6f42c1",
            "数据泄露": "#e83e8c", "软件问题": "#0d6efd", "其他": "#6c757d",
        }
        fallback = "#6c757d"
        cat_html = " ".join(
            f"<span style='background:{cat_colors.get(c, fallback)};color:white;padding:2px 8px;border-radius:10px;font-size:0.85em;margin-right:4px;'>{c}</span>"
            for c in categories
        )
        st.markdown(cat_html, unsafe_allow_html=True)

    # -------- 评论区红绿灯 --------
    comments_analysis = result.get("评论区分析")
    if comments_analysis:
        st.divider()
        st.subheader("评论区红绿灯")

        tl = comments_analysis.get("评论红绿灯", {})
        red = tl.get("红", 0)
        yellow = tl.get("黄", 0)
        green = tl.get("绿", 0)
        total = red + yellow + green

        if total > 0:
            st.markdown(
                f"<div style='display:flex;height:32px;border-radius:6px;overflow:hidden;margin:10px 0;'>"
                + (f"<div style='width:{red/total*100}%;background:#dc3545;' title='负面 {red}'></div>" if red else "")
                + (f"<div style='width:{yellow/total*100}%;background:#ffc107;' title='中性 {yellow}'></div>" if yellow else "")
                + (f"<div style='width:{green/total*100}%;background:#28a745;' title='正面 {green}'></div>" if green else "")
                + "</div>",
                unsafe_allow_html=True,
            )

            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                st.metric("负面", red)
            with rc2:
                st.metric("中性", yellow)
            with rc3:
                st.metric("正面", green)

        st.caption(f"评论总结: {comments_analysis.get('评论总结', '')}")

        details = comments_analysis.get("评论详情", [])
        if details:
            with st.expander(f"查看 {len(details)} 条评论详情", expanded=False, key=f"{key_prefix}comment_details_expander"):
                for d in details:
                    emoji_map = {"正面": "\U0001f7e2", "中性": "\U0001f7e1", "负面": "\U0001f534"}
                    emoji = emoji_map.get(d.get("情感", ""), "⚪")
                    st.markdown(f"{emoji} **[{d.get('情感', '?')}]** {d.get('内容', '')}")
                    if d.get("关键短语"):
                        st.caption(f"  → {d.get('关键短语')}")

    # -------- 完整 JSON --------
    with st.expander("查看完整 JSON", expanded=False, key=f"{key_prefix}full_json_expander"):
        display_result = {k: v for k, v in result.items() if k != "_meta"}
        st.json(display_result)

    # -------- Token 用量 --------
    meta = result.get("_meta", {})
    usage = meta.get("usage", {})
    if usage:
        st.caption(
            f"Token: 输入 {usage.get('input_tokens','?')} | 输出 {usage.get('output_tokens','?')} | 模型 {meta.get('model','?')}"
        )

    # ═══════════════════════════════════════════════════════════════════
    # 标注历史回溯
    # ═══════════════════════════════════════════════════════════════════
    url_for_history = st.session_state.get("scraped_data", {}).get("原文链接", "")
    if url_for_history:
        history = find_annotation_history(url_for_history)
        if len(history) >= 2:
            with st.expander(f"\U0001f4dc 标注历史 ({len(history)} 次记录)", expanded=False, key=f"{key_prefix}history_expander"):
                for h_idx, h in enumerate(history):
                    a = h["annotation"]
                    sev = a.get("严重度评级", "?")
                    act = a.get("分流建议", "?")
                    sent = a.get("情感分析", {}).get("整体情感", "?")
                    st.caption(f"**{h['date']}** — {sev} | {act} | {sent}")
                    if h_idx + 1 < len(history):
                        diffs = diff_annotations(history[h_idx + 1]["annotation"], a)
                        if diffs:
                            for d in diffs:
                                st.markdown(
                                    f"- {d['label']}: `{d['old_value']}` → **`{d['new_value']}`**"
                                )
                        else:
                            st.caption("  (无变化)")
                    if h_idx < len(history) - 1:
                        st.divider()

    # ═══════════════════════════════════════════════════════════════════
    # 纠偏功能
    # ═══════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("纠偏（修正 AI 标注）")

    with st.expander("点击展开纠偏表单", expanded=False, key=f"{key_prefix}correction_form_expander"):
        st.markdown("修改你认为 AI 判断不准确的字段，然后点击保存。差异显著时将自动生成校准案例。")

        corr_severity = st.selectbox(
            "严重度评级",
            ["P0", "P1", "P2", "P3"],
            index=["P0", "P1", "P2", "P3"].index(severity) if severity in ["P0", "P1", "P2", "P3"] else 2,
            key=f"{key_prefix}corr_severity",
        )
        corr_action = st.selectbox(
            "分流建议",
            ["立即处理", "持续观察", "可忽略", "正面可利用"],
            index=["立即处理", "持续观察", "可忽略", "正面可利用"].index(action) if action in ["立即处理", "持续观察", "可忽略", "正面可利用"] else 1,
            key=f"{key_prefix}corr_action",
        )
        corr_sentiment = st.selectbox(
            "整体情感",
            ["正面", "负面", "中性", "混合"],
            index=["正面", "负面", "中性", "混合"].index(sentiment) if sentiment in ["正面", "负面", "中性", "混合"] else 3,
            key=f"{key_prefix}corr_sentiment",
        )
        corr_categories = st.multiselect(
            "舆情分类",
            CATEGORY_OPTIONS,
            default=categories if isinstance(categories, list) else [],
            key=f"{key_prefix}corr_categories",
        )
        corr_summary = st.text_area("摘要", value=result.get("摘要", ""), key=f"{key_prefix}corr_summary")
        corr_reason = st.text_area("严重度理由", value=result.get("严重度理由", ""), key=f"{key_prefix}corr_reason")

        # ---------- 评论区修正 ----------
        comments_analysis = result.get("评论区分析") or {}
        ai_comment_details = comments_analysis.get("评论详情", [])
        ai_traffic = comments_analysis.get("评论红绿灯", {})

        st.divider()
        st.markdown("#### 评论区修正")

        corr_comment_summary = st.text_area(
            "评论总结",
            value=comments_analysis.get("评论总结", ""),
            key=f"{key_prefix}corr_comment_summary",
            placeholder="一句话概括评论区整体风向...",
        )

        corrected_sentiments = []
        if ai_comment_details:
            st.caption(f"逐条修正情感（共 {len(ai_comment_details)} 条）")
            for i, d in enumerate(ai_comment_details):
                original_sentiment = d.get("情感", "中性")
                new_sentiment = st.selectbox(
                    f"#{i + 1} {d.get('内容', '')[:40]}...",
                    ["正面", "中性", "负面"],
                    index=["正面", "中性", "负面"].index(original_sentiment) if original_sentiment in ["正面", "中性", "负面"] else 1,
                    key=f"{key_prefix}corr_comment_{i}",
                )
                corrected_sentiments.append(new_sentiment)

            if corrected_sentiments:
                red = corrected_sentiments.count("负面")
                yellow = corrected_sentiments.count("中性")
                green = corrected_sentiments.count("正面")
                total = red + yellow + green
                if total > 0:
                    st.markdown(
                        f"修正后红绿灯：\U0001f534 {red}  \U0001f7e1 {yellow}  \U0001f7e2 {green}"
                        + f"  |  AI原始：\U0001f534{ai_traffic.get('红','?')} \U0001f7e1{ai_traffic.get('黄','?')} \U0001f7e2{ai_traffic.get('绿','?')}"
                    )

        corr_note = st.text_input("纠偏备注（可选）", placeholder="为什么这样修正...", key=f"{key_prefix}corr_note")

        if st.button("保存纠偏", type="primary", key=f"{key_prefix}save_correction"):
            human_correction = dict(result)
            human_correction["严重度评级"] = corr_severity
            human_correction["分流建议"] = corr_action
            if "情感分析" not in human_correction:
                human_correction["情感分析"] = {}
            human_correction["情感分析"]["整体情感"] = corr_sentiment
            human_correction["摘要"] = corr_summary
            human_correction["严重度理由"] = corr_reason
            human_correction["舆情分类"] = corr_categories

            if ai_comment_details and corrected_sentiments:
                new_details = []
                for i, d in enumerate(ai_comment_details):
                    new_d = dict(d)
                    new_d["情感"] = corrected_sentiments[i]
                    new_details.append(new_d)
                human_correction["评论区分析"] = {
                    "评论红绿灯": {
                        "红": corrected_sentiments.count("负面"),
                        "黄": corrected_sentiments.count("中性"),
                        "绿": corrected_sentiments.count("正面"),
                    },
                    "评论详情": new_details,
                    "评论总结": corr_comment_summary,
                }
            elif corr_comment_summary and corr_comment_summary != comments_analysis.get("评论总结", ""):
                human_correction["评论区分析"] = dict(comments_analysis)
                human_correction["评论区分析"]["评论总结"] = corr_comment_summary

            ai_output_clean = {k: v for k, v in result.items() if k != "_meta"}

            correction_result = handle_correction(
                original_input=st.session_state.scraped_data or {},
                ai_output=ai_output_clean,
                human_correction=human_correction,
                url=st.session_state.get("url_input", ""),
            )
            st.session_state.correction_result = correction_result

            if correction_result["action"] == "generated_case":
                st.success(f"已生成新校准案例: {correction_result['case_file']}")
                st.info("下一轮标注将受此案例校准。请刷新知识库以加载新案例。")
            elif correction_result["action"] == "logged_only":
                st.info("差异较小，已记录日志（不生成新案例）。")
            else:
                st.info("未检测到差异。")

    # 纠偏结果反馈
    if st.session_state.correction_result:
        cr = st.session_state.correction_result
        if cr["action"] != "no_change" and cr.get("diffs"):
            st.markdown("**检测到的差异：**")
            for field, vals in cr["diffs"].items():
                st.markdown(f"- {field}: `{vals['ai']}` → `{vals['human']}`")

    # Ingest 结果反馈
    if st.session_state.ingest_result:
        ir = st.session_state.ingest_result
        if ir["action"] == "case_generated":
            st.success(f"知识库已自动更新: {ir['case_file']}")
            bc = ir.get("boundary_check", {})
            flags = []
            if bc.get("p1_uncovered"):
                flags.append("P1 覆盖盲区已填补")
            if bc.get("unusual_combo"):
                flags.append("异常严重度-分流组合")
            if bc.get("new_platform"):
                flags.append("新平台覆盖")
            if flags:
                st.info(f"边界提醒: {'; '.join(flags)}")
            suggestions = ir.get("boundary_suggestions", [])
            if suggestions:
                with st.expander("\U0001f4dd 建议更新知识库概念页（Draft PR）", expanded=False):
                    st.caption("以下修改建议基于本次标注发现的边界盲区自动生成，不会直接写入。请审阅后手动应用。")
                    for j, s in enumerate(suggestions):
                        st.markdown(f"**建议 {j+1}**: {s['title']}")
                        st.caption(f"触发: {s['trigger']} | 目标文件: {s['target_file']} | 区域: {s['section']}")
                        st.info(s['reason'])
                        st.markdown(f"```diff\n+ {s['proposed_text']}\n```")
                        if j < len(suggestions) - 1:
                            st.divider()
        elif ir["action"] == "skipped":
            st.caption(f"知识库: 已有案例 {ir['case_file']}，跳过自动 Ingest。")


# ═══════════════════════════════════════════════════════════════════════════════
# Annotation helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _save_annotation_output(
    scraped_data: dict,
    annotation_result: dict,
    url: str = "",
) -> str | None:
    platform = scraped_data.get("来源平台", "未知")
    today = date.today().isoformat()
    content_id = _extract_content_id(url, platform) if url else "manual"
    abbrev = PLATFORM_ABBREV.get(platform, "web")
    filename = f"{today}_{abbrev}_{content_id}_annotation.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    payload = {
        "scraped_data": scraped_data,
        "annotation_result": annotation_result,
        "ingested_at": datetime.now().isoformat(),
    }
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return filename
    except OSError:
        return None


def _do_ingest(scraped_data: dict, annotation_result: dict, url: str = "") -> dict:
    try:
        return ingest(scraped_data, annotation_result, url)
    except Exception as e:
        return {"action": "error", "case_file": None, "boundary_check": {}, "_ingest_error": str(e)}


def _clear_correction_widgets():
    for key in list(st.session_state.keys()):
        if key.startswith("corr_") or key.startswith("tab1_corr_") or key.startswith("tab2_corr_"):
            del st.session_state[key]


def do_scrape(url: str):
    with st.spinner(f"正在抓取 {url[:60]}..."):
        data = scrape(url)
        st.session_state.scraped_data = data
        st.session_state.annotation_result = None
        st.session_state.correction_result = None
        st.session_state.ingest_result = None
        _clear_correction_widgets()
    return data
