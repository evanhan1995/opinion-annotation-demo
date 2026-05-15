# -*- coding: utf-8 -*-
"""Tab 1: Manual entry — fill all fields by hand, save to knowledge base.

Extracted from app.py — no logic changes, pure code movement.
"""

import streamlit as st
from engine.annotate import CATEGORY_OPTIONS
from ui.shared import _do_ingest, _save_annotation_output


def render_tab1():
    """Render the manual entry tab (Tab 1)."""

    st.caption("适用于小红书/YTB之外的平台内容，或无法自动抓取的内容。所有字段人工填写。")

    # --- txt upload → AI summary ---
    uploaded_file = st.file_uploader("📎 上传 txt 文件（AI 自动总结）", type=["txt"], key="manual_upload")
    ai_summary_btn = st.button("🤖 AI 总结上传内容", disabled=not bool(uploaded_file), key="ai_summary_btn",
                               help="读取上传的 txt 内容，AI 生成简介摘要")

    if ai_summary_btn and uploaded_file:
        try:
            txt_content = uploaded_file.read().decode("utf-8")
            st.session_state.manual_content = txt_content[:5000]
            config = st.session_state.config
            if config and config.get("api_key"):
                from openai import OpenAI
                client = OpenAI(api_key=config["api_key"], base_url=config["api_base"])
                resp = client.chat.completions.create(
                    model=config["model"], max_tokens=200, temperature=0.3, timeout=30,
                    messages=[{"role": "user", "content": f"请用80字以内总结以下内容的核心问题、涉及品牌/产品、舆论倾向：\n\n{txt_content[:3000]}"}],
                )
                st.session_state.manual_summary = resp.choices[0].message.content.strip()
                st.success("AI 总结已生成")
            else:
                st.warning("请先在侧边栏加载知识库（配置 API Key）")
        except Exception as e:
            st.error(f"上传失败: {e}")

    # --- URL & Platform ---
    c1, c2, c3 = st.columns(3)
    with c1:
        manual_url = st.text_input("原文链接 *", placeholder="https://...  （必填，用于知识库溯源）", key="manual_url")
    with c2:
        manual_platform = st.selectbox("来源平台", ["小红书", "YouTube", "Instagram", "TikTok", "X (Twitter)", "Reddit", "新闻媒体", "论坛", "其他"], key="manual_platform")
    with c3:
        manual_publish_time = st.text_input("发布时间", placeholder="2025-01-15", key="manual_publish_time")

    manual_author = st.text_input("作者名称", key="manual_author")

    # --- 社媒数据 ---
    with st.expander("📊 社媒数据（选填）", expanded=False):
        s1, s2, s3, s4 = st.columns(4)
        with s1: manual_views = st.text_input("播放量", placeholder="0", key="manual_views")
        with s2: manual_likes = st.text_input("点赞数", placeholder="0", key="manual_likes")
        with s3: manual_followers = st.text_input("粉丝数", placeholder="0", key="manual_followers")
        with s4: manual_country = st.text_input("国家", placeholder="CN/US/...", key="manual_country")
        manual_homepage = st.text_input("作者主页 URL", placeholder="https://...", key="manual_homepage")

    # --- 分类 & 评定 ---
    d1, d2 = st.columns(2)
    with d1:
        manual_categories = st.multiselect("舆情分类", CATEGORY_OPTIONS, key="manual_categories")
        manual_severity = st.selectbox("严重度评级", ["P0", "P1", "P2", "P3"], index=2, key="manual_severity")
    with d2:
        manual_action = st.selectbox("分流建议", ["立即处理", "持续观察", "可忽略", "正面可利用"], index=1, key="manual_action")
        manual_sentiment = st.selectbox("整体情感", ["正面", "负面", "中性", "混合"], index=2, key="manual_sentiment")

    manual_summary = st.text_area("简介 *", placeholder="案例摘要（必填。可上传 txt 后 AI 自动填充）", height=120, key="manual_summary")
    manual_reason = st.text_input("严重度理由", placeholder="为什么评定这个严重度...", key="manual_reason")

    # --- Save + Next ---
    sc1, sc2 = st.columns([2, 1])
    with sc1:
        if st.button("💾 保存到知识库", type="primary", use_container_width=True, disabled=not (manual_url.strip() and manual_summary.strip())):
            scraped = {
                "原文内容": manual_summary.strip(),
                "来源平台": manual_platform,
                "发布者类型": f"用户: {manual_author}" if manual_author else "未知",
                "互动数据": "",
                "发布时间": manual_publish_time or "",
                "原文链接": manual_url.strip(),
                "评论列表": [],
                "社媒数据": {
                    "作者": manual_author or "未知", "国家": manual_country,
                    "点赞": int(manual_likes) if manual_likes.isdigit() else 0,
                    "评论": 0,
                    "粉丝": int(manual_followers) if manual_followers.isdigit() else 0,
                    "播放量": int(manual_views) if manual_views.isdigit() else None,
                    "时长": "", "作者主页": [manual_homepage] if manual_homepage.strip() else [],
                } if any([manual_author, manual_country, manual_likes, manual_followers, manual_views, manual_homepage.strip()]) else None,
            }
            annotation = {
                "严重度评级": manual_severity, "分流建议": manual_action,
                "情感分析": {"整体情感": manual_sentiment},
                "摘要": manual_summary.strip(), "严重度理由": manual_reason or "人工录入",
                "风险标签": [], "舆情分类": manual_categories,
            }
            st.session_state.scraped_data = scraped
            st.session_state.annotation_result = annotation
            st.session_state._result_source = "manual"
            _save_annotation_output(scraped, annotation)
            st.session_state.ingest_result = _do_ingest(scraped, annotation)
            st.success("已保存到知识库！")
            st.session_state._needs_rerun = True
    with sc2:
        if st.button("📋 下一个案例", use_container_width=True, help="清空表单，准备录入下一条"):
            for k in ["manual_url", "manual_author", "manual_views", "manual_likes", "manual_followers",
                       "manual_country", "manual_homepage", "manual_summary", "manual_reason", "manual_publish_time"]:
                if k in st.session_state: del st.session_state[k]
            st.rerun()

    if st.session_state.ingest_result:
        ir = st.session_state.ingest_result
        if ir["action"] == "case_generated":
            st.success(f"知识库已更新: {ir['case_file']}")
