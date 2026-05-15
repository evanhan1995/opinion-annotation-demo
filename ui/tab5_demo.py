# -*- coding: utf-8 -*-
"""Tab 5: Demo walkthrough — simulated full pipeline, no API calls, no writes.

Extracted from app.py — no logic changes, pure code movement.
"""

import streamlit as st
from ui.shared import _clear_correction_widgets, _render_annotation_result

# ═══════════════════════════════════════════════════════════════════════════════
# Demo data (offline simulation)
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_URL = "https://www.youtube.com/watch?v=DIBL7PKlzaU"
DEMO_SCRAPED = {
    "原文内容": "标题：Temu Pinduoduo Flooded With Fakes & Trash\n\n描述：From earlier days of Taobao to Pinduoduo and TikTok Shop, counterfeit and inferior products are rampant on Chinese e-commerce platforms. This investigation reveals the scale of the problem.\n\n时长：18分0秒",
    "来源平台": "YouTube",
    "发布者类型": "YouTuber: China Observer, 814,000订阅",
    "互动数据": "播放1,013,104, 点赞14,371, 评论7,626",
    "发布时间": "2023-11-22",
    "评论列表": [
        {"内容": "Temu is literally just a scam marketplace at this point", "点赞": "3200"},
        {"内容": "I ordered something and never received it, customer service was useless", "点赞": "1800"},
        {"内容": "The quality is exactly what you pay for - nothing", "点赞": "950"},
        {"内容": "Finally someone is talking about this! I've been saying this for months", "点赞": "2100"},
        {"内容": "Pinduoduo has been doing this for years in China, now they export the same model", "点赞": "1500"},
        {"内容": "My credit card got charged multiple times for one order", "点赞": "870"},
        {"内容": "It's literally just AliExpress with better marketing", "点赞": "630"},
    ],
    "社媒数据": {
        "作者": "China Observer", "国家": "US", "点赞": 14371, "评论": 7626,
        "粉丝": 814000, "播放量": 1013104, "时长": "18分0秒",
        "作者主页": ["https://www.youtube.com/@ChinaObserver"],
    },
}

DEMO_ANNOTATION = {
    "严重度评级": "P1",
    "分流建议": "立即处理",
    "情感分析": {"整体情感": "负面"},
    "摘要": "814K粉YouTuber指控Temu/Pinduoduo充斥假货劣质品，播放超100万，评论区大比例负面，号召抵制",
    "严重度理由": "中危内容(产品质量指控)×高影响力(814K粉+100万播放)，评论区呈加速传播态势",
    "分流理由": "涉及品牌核心价值攻击+大规模传播，需立即响应并监测跨平台扩散",
    "风险标签": ["商品质量", "KOL负面", "大规模传播", "消费者信任"],
    "舆情分类": ["商品问题", "商品侵权问题"],
    "评论区分析": {
        "评论红绿灯": {"红": 5, "黄": 1, "绿": 1},
        "评论总结": "前排评论压倒性负面，用户指控诈骗/质量低劣/客服无效，出现号召抵制倾向",
    },
}

DEMO_SIMILAR = [
    {"filename": "case-015.md", "title": "Nathan Espinoza指控Temu为间谍软件", "severity": "P0", "hits": 3},
    {"filename": "case-011.md", "title": "TEMU商品质量+客服投诉", "severity": "P1", "hits": 2},
    {"filename": "case-018.md", "title": "China Observer深度调查中国电商假货", "severity": "P2", "hits": 2},
]


# ═══════════════════════════════════════════════════════════════════════════════
# Tab renderer
# ═══════════════════════════════════════════════════════════════════════════════

def render_tab5():
    """Render the demo walkthrough tab (Tab 5)."""

    st.subheader("🎬 操作演示")
    st.caption("模拟完整 URL 抓取→AI 标注→纠偏流程。全程离线，不调用 API，不写入知识库。")

    demo_step = st.session_state.get("demo_step", 0)

    # Step 0: Input URL
    if demo_step == 0:
        st.info("**Step 1/4**: 输入舆情链接")
        demo_url = st.text_input("粘贴舆情链接", value=DEMO_URL, key="demo_url")
        if st.button("抓取并标注 →", type="primary", use_container_width=True, key="demo_start"):
            st.session_state.demo_step = 1
            st.session_state._needs_rerun = True

    # Step 1: Simulated scraping
    elif demo_step == 1:
        st.info("**Step 2/4**: 正在抓取内容...")
        with st.spinner("正在抓取 YouTube 内容..."):
            import time as _time
            _time.sleep(1.5)
        st.success("抓取完成！")
        st.session_state.scraped_data = DEMO_SCRAPED
        st.session_state.demo_step = 2
        st.rerun()

    # Step 2: Simulated annotation
    elif demo_step == 2:
        st.info("**Step 3/4**: AI 正在分析标注...")
        progress = st.empty()
        for pct in (20, 50, 80, 100):
            import time as _time
            _time.sleep(0.4)
            progress.info(f"AI 正在分析... (已生成 {pct * 3} 字符)")
        progress.empty()
        st.success("标注完成！")
        st.session_state.annotation_result = DEMO_ANNOTATION
        st.session_state._result_source = "demo"
        st.session_state.demo_step = 3
        st.rerun()

    # Step 3: Show result + similar cases + correction
    elif demo_step == 3:
        st.info("**Step 4/4**: 查看标注结果 & 操作")
        _render_annotation_result("demo_")

        st.divider()
        if st.button("🔄 重新演示", use_container_width=True, key="demo_reset"):
            st.session_state.demo_step = 0
            st.session_state.annotation_result = None
            st.session_state.scraped_data = None
            _clear_correction_widgets()
            st.session_state._needs_rerun = True

        st.caption("⚠️ 以上为模拟数据，不会写入知识库。实际操作请在「URL 抓取」标签页进行。")
