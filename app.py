"""舆情智能标注系统 —— Web 界面

使用方法:
    streamlit run app.py
    然后在浏览器中打开 http://localhost:8501
"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

# 路径设置（确保能 import engine 模块）
PROJECT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = PROJECT_DIR / "engine"
OUTPUT_DIR = PROJECT_DIR / "outputs"
sys.path.insert(0, str(PROJECT_DIR))

import streamlit as st
from engine.scraper import scrape, SCRAPERS, _detect_platform, _extract_content_id, PLATFORM_ABBREV
from engine.annotate import (
    build_system_prompt,
    load_config,
    format_user_message,
    annotate_one,
    annotate_one_stream,
)
from engine.correction_handler import handle_correction
from engine.ingestor import ingest

# Startup sanity check: verify all scrapers importable
_supported = list(SCRAPERS.keys())
print(f"[Scraper] Supported platforms: {_supported}")
if "小红书" not in _supported:
    print("[Scraper] WARNING: XHS scraper NOT loaded! Restart Streamlit after updating code.")

# ═══════════════════════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="舆情智能标注系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("舆情智能标注系统")
st.caption("基于 Wiki 知识库 + LLM 的智能打标与分流判断")

# Demo guide: show once per session
if "demo_guide_shown" not in st.session_state:
    st.session_state.demo_guide_shown = False
if not st.session_state.demo_guide_shown and not st.session_state.annotation_result:
    with st.expander("👋 快速入门指南", expanded=True):
        st.markdown("""
        1. **加载 Demo** → 点击左侧「📝 手动输入」标签页中的「📋 加载 Demo 示例」
        2. **AI 标注** → 点击「标注」按钮，等待 AI 分析结果
        3. **查看案例** → 切换到「📚 知识库」标签页，从左侧选择案例查看
        4. **尝试纠偏** → 在标注结果底部的「纠偏」表单中修改 AI 判断，保存后自动生成校准案例
        5. **问答检索** → 切换到「💬 扫地僧」标签页，向知识库提问
        """)
        if st.button("知道了，开始使用", key="dismiss_guide"):
            st.session_state.demo_guide_shown = True
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# 初始化 session state
# ═══════════════════════════════════════════════════════════════════════════════

for key, default in [
    ("scraped_data", None),
    ("annotation_result", None),
    ("correction_result", None),
    ("ingest_result", None),
    ("agent_messages", []),
    ("system_prompt_loaded", False),
    ("kb_stats", None),
    ("config", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ═══════════════════════════════════════════════════════════════════════════════
# 侧边栏：系统状态
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.subheader("系统状态")

    if st.button("加载/刷新知识库"):
        with st.spinner("加载 Wiki 知识库..."):
            config = load_config()
            system_prompt, kb_stats = build_system_prompt()
            st.session_state.config = config
            st.session_state.system_prompt_loaded = True
            st.session_state.kb_stats = kb_stats

    if st.session_state.system_prompt_loaded:
        kb = st.session_state.kb_stats
        loaded = sum(1 for v in kb["layers"].values() if v["status"] == "loaded")
        st.success(f"知识库: {loaded}/{len(kb['layers'])} 页 (~{kb['total_estimated_tokens']} tokens)")
        st.info(f"模型: {st.session_state.config.get('model', '?')}")
        st.info(f"Provider: {st.session_state.config.get('provider', '?')}")
    else:
        st.warning("请先加载知识库")
        # 自动加载
        if st.session_state.config is None:
            config = load_config()
            system_prompt, kb_stats = build_system_prompt()
            st.session_state.config = config
            st.session_state.system_prompt_loaded = True
            st.session_state.kb_stats = kb_stats
            st.rerun()

    api_key = (st.session_state.config or {}).get("api_key", "")
    if api_key:
        st.success("API Key: 已配置")
    else:
        st.error("API Key: 未配置")

    # Dashboard (auto-refresh from disk)
    st.divider()
    with st.expander("📊 系统仪表盘", expanded=False):
        try:
            from datetime import date as _date
            wiki_dir = PROJECT_DIR / "wiki"
            cases_dir = wiki_dir / "cases"
            case_files = sorted(cases_dir.glob("case-*.md"))
            total = len(case_files)

            sev_count = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
            plat_count = {}
            for cf in case_files:
                text = cf.read_text(encoding="utf-8")
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].split("\n"):
                        line = line.strip()
                        if line.startswith("severity:"):
                            s = line.split(":")[1].strip()
                            if s in sev_count:
                                sev_count[s] += 1
                        elif line.startswith("platform:"):
                            p = line.split(":")[1].strip()
                            if p and p != "?":
                                plat_count[p] = plat_count.get(p, 0) + 1

            c1, c2 = st.columns(2)
            with c1:
                st.metric("案例总数", total)
            with c2:
                p1_count = sev_count.get("P1", 0)
                st.metric("P0/P1 高优", sev_count.get("P0", 0) + p1_count)

            st.caption(f"P0: {sev_count['P0']} | P1: {sev_count['P1']} | P2: {sev_count['P2']} | P3: {sev_count['P3']}")

            if plat_count:
                plat_items = sorted(plat_count.items(), key=lambda x: -x[1])
                st.caption("  |  ".join(f"{k}: {v}" for k, v in plat_items))

            # Recent log entries
            log_path = wiki_dir / "log.md"
            if log_path.exists():
                log_lines = log_path.read_text(encoding="utf-8").strip().split("\n")
                recent = [l for l in log_lines if l.startswith("### ")][-3:]
                if recent:
                    st.caption("---")
                    st.caption("最近操作:")
                    for r in recent:
                        st.caption(r.strip("# ")[:60])
        except Exception:
            st.caption("(仪表盘加载失败)")

    # 纠偏率监控
    try:
        log_path = PROJECT_DIR / "wiki" / "log.md"
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8")
            total_ingests = log_text.count("自动Ingest")
            total_corrections = log_text.count("纠偏")
            total_ops = total_ingests + total_corrections
            if total_ops > 0:
                accuracy = round((1 - total_corrections / total_ops) * 100)
                st.divider()
                st.caption(f"AI 标注准确率: {accuracy}% ({total_ops} 次操作, {total_corrections} 次纠偏)")
                color = "#28a745" if accuracy >= 80 else "#ffc107" if accuracy >= 60 else "#dc3545"
                st.markdown(
                    f"<div style='background:{color};height:6px;border-radius:3px;width:{accuracy}%'></div>",
                    unsafe_allow_html=True,
                )
    except Exception:
        pass

    # XHS Cookie 状态
    try:
        import json as _json
        from datetime import datetime as _dt
        cookie_file = ENGINE_DIR / ".xhs_cookies.json"
        if cookie_file.exists():
            with open(cookie_file, "r", encoding="utf-8") as _f:
                cookie_data = _json.load(_f)
            saved_ts = cookie_data.get("saved_at", 0)
            if saved_ts:
                saved_dt = _dt.fromtimestamp(saved_ts)
                days_left = 7 - (_dt.now() - saved_dt).days
                if days_left <= 0:
                    st.error("小红书 Cookie 已过期，请刷新登录")
                elif days_left <= 1:
                    st.warning(f"小红书 Cookie 即将过期 (剩余 {days_left} 天)")
                else:
                    st.caption(f"小红书 Cookie: 剩余 {days_left} 天")
    except Exception:
        pass

    st.divider()
    st.subheader("小红书登录")
    if st.button("刷新小红书登录", use_container_width=True):
        from engine.xhs_fetcher import bootstrap_cookies
        with st.spinner("正在打开浏览器，请扫码登录..."):
            cookie = bootstrap_cookies(force=True)
            if cookie:
                st.success("小红书登录成功！")
            else:
                st.error("登录失败或超时，请重试")

# ═══════════════════════════════════════════════════════════════════════════════
# Demo 数据
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_DATA = {
    "原文内容": (
        "标题：某品牌新品发布会后网友炸锅了\n\n"
        "正文：今天参加了XX品牌的新品发布会，现场展示的产品功能确实让人眼前一亮。"
        "但回到价格环节，全场鸦雀无声——起售价直接比上一代涨了40%，"
        "配置升级却只有小幅迭代。不少媒体同行当场表示'定价策略有问题'。"
        "不过也有粉丝认为品牌溢价合理，毕竟生态体验确实好。大家怎么看？"
    ),
    "来源平台": "小红书",
    "发布者类型": "KOL (粉丝量 12万)",
    "互动数据": "点赞 3.2万，收藏 8900，评论 4200，分享 1500",
    "评论列表": [
        {"内容": "太贵了，这个价格我为什么不买竞品？人家配置还更高", "点赞": "2300"},
        {"内容": "用过的人表示生态体验确实值这个价，别只看参数", "点赞": "1800"},
        {"内容": "作为老用户感觉被背刺了，上一代买完半年就出新款", "点赞": "950"},
        {"内容": "弱弱问一句，这个和之前那个版本有什么区别吗？", "点赞": "320"},
        {"内容": "已下单，信仰充值，不解释", "点赞": "1500"},
        {"内容": "理性讨论，这个定价策略是不是在清上一代库存？", "点赞": "670"},
        {"内容": "对比了一下参数，升级幅度确实小，不如等下一代", "点赞": "430"},
        {"内容": "说贵的都是没用过的吧，用了就知道真香", "点赞": "1200"},
    ],
}

def load_demo():
    """Fill session state with demo data."""
    d = DEMO_DATA
    st.session_state.manual_content = d["原文内容"]
    st.session_state.manual_platform = d["来源平台"]
    st.session_state.manual_publisher = d["发布者类型"]
    st.session_state.manual_engagement = d["互动数据"]
    st.session_state.manual_comments = "\n".join(c["内容"] for c in d["评论列表"])


# ═══════════════════════════════════════════════════════════════════════════════
# Wiki 浏览器辅助函数
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
    dir_order = ["concepts", "entities", "sources", "syntheses", "cases"]

    for dirname in dir_order:
        dir_path = wiki_dir / dirname
        if not dir_path.exists():
            continue
        files = sorted(dir_path.glob("*.md"))
        # Exclude index.md files, handle separately
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
            label = f"📖 {c['title'][:20]}"
            if st.button(label, key=f"cite_{c['path']}_{i}", use_container_width=True):
                st.session_state._selected_page = c["path"]
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 主区域：输入
# ═══════════════════════════════════════════════════════════════════════════════

def _render_annotation_result(key_prefix: str = ""):
    """Render annotation result display. Only called inside annotation tabs.

    key_prefix distinguishes widgets between Tab1/Tab2 to avoid duplicate key errors.
    """
    result = st.session_state.annotation_result
    if not result:
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

    # -------- 严重度卡片 --------
    severity = result.get("严重度评级", "?")
    action = result.get("分流建议", "?")
    sentiment = result.get("情感分析", {}).get("整体情感", "?")

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

    # -------- 风险标签 --------
    tags = result.get("风险标签", [])
    if tags:
        st.write(" ".join([f"`{t}`" for t in tags]))

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
                    emoji_map = {"正面": "🟢", "中性": "🟡", "负面": "🔴"}
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
                        f"修正后红绿灯：🔴 {red}  🟡 {yellow}  🟢 {green}"
                        + f"  |  AI原始：🔴{ai_traffic.get('红','?')} 🟡{ai_traffic.get('黄','?')} 🟢{ai_traffic.get('绿','?')}"
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
        elif ir["action"] == "skipped":
            st.caption(f"知识库: 已有案例 {ir['case_file']}，跳过自动 Ingest。")


tab1, tab2, tab3, tab4 = st.tabs(["📝 手动输入", "🔗 URL 抓取", "📚 知识库", "💬 扫地僧"])

with tab1:
    # Demo button
    demo_col1, demo_col2 = st.columns([1, 3])
    with demo_col1:
        if st.button("📋 加载 Demo 示例", use_container_width=True):
            load_demo()
            st.rerun()

    manual_content = st.text_area(
        "原文内容",
        placeholder="把帖文/评论/视频描述原文粘贴在这里，或点击上方「加载 Demo 示例」体验完整流程...",
        height=150,
        key="manual_content",
    )
    mcol1, mcol2, mcol3 = st.columns(3)
    with mcol1:
        manual_platform = st.selectbox(
            "来源平台",
            ["小红书", "YouTube", "Instagram", "TikTok", "X (Twitter)", "Reddit", "新闻媒体", "论坛", "其他"],
            key="manual_platform",
        )
    with mcol2:
        manual_publisher = st.text_input("发布者类型", placeholder="普通用户 / KOL(粉丝量) / 媒体", key="manual_publisher")
    with mcol3:
        manual_engagement = st.text_input("互动数据", placeholder="点赞XX，转发XX，评论XX", key="manual_engagement")

    manual_comments = st.text_area(
        "评论区内容（选填，每行一条）",
        placeholder="评论1\n评论2\n评论3\n...（最多10条）",
        height=100,
        key="manual_comments",
    )
    manual_annotate_btn = st.button("标注", type="primary", use_container_width=True,
                                    disabled=not bool(manual_content.strip()))

    _render_annotation_result("tab1_")

with tab2:
    st.info("URL 抓取需要本地浏览器环境，在线 Demo 不可用。建议使用左侧「📝 手动输入」标签页，或点击「📋 加载 Demo 示例」快速体验。")
    url_input = st.text_input(
        "粘贴舆情链接",
        placeholder="https://www.xiaohongshu.com/explore/... 或 https://www.youtube.com/watch?v=...",
        key="url_input",
    )
    col1, col2 = st.columns([1, 1])
    with col1:
        scrape_btn = st.button("抓取内容", type="primary", use_container_width=True,
                               disabled=not bool(url_input.strip()))
    with col2:
        annotate_scraped_btn = st.button("抓取并标注", type="secondary", use_container_width=True,
                                         disabled=not bool(url_input.strip()))

    _render_annotation_result("tab2_")

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 3: 知识库浏览器
# ═══════════════════════════════════════════════════════════════════════════════

with tab3:
    st.subheader("📚 知识库浏览器")

    pages = _load_wiki_pages()

    col_nav, col_content = st.columns([1, 3])

    with col_nav:
        st.caption("按类型浏览")

        type_labels = {
            "concepts": ("🔬 Concepts", True),
            "entities": ("🏢 Entities", True),
            "sources": ("📄 Sources", True),
            "syntheses": ("🔗 Syntheses", True),
            "cases": ("📋 Cases", True),
        }

        for dirname, (label, default_expanded) in type_labels.items():
            group = [p for p in pages if p["dir"] == dirname]
            if not group:
                continue
            with st.expander(f"{label} ({len(group)})", expanded=default_expanded):
                for p in group:
                    is_selected = st.session_state.get("_selected_page") == p["path"]
                    btn_label = f"> {p['title'][:35]}" if not is_selected else f"**>> {p['title'][:35]}**"
                    if st.button(
                        btn_label,
                        key=f"nav_{p['path']}",
                        use_container_width=True,
                    ):
                        st.session_state._selected_page = p["path"]
                        st.rerun()

        st.divider()
        st.caption("📜 操作日志")
        if st.button("🔄 刷新", use_container_width=True, key="refresh_wiki"):
            st.rerun()

    with col_content:
        selected = st.session_state.get("_selected_page")
        page_paths = {p["path"]: p for p in pages}

        if selected and selected in page_paths:
            page_data = page_paths[selected]
            md_content = _convert_wikilinks(page_data["content"])
            st.markdown(md_content)
        else:
            st.info("👈 从左侧选择一个页面来浏览")
            log_path = PROJECT_DIR / "wiki" / "log.md"
            if log_path.exists():
                log_lines = log_path.read_text(encoding="utf-8").strip().split("\n")
                last_20 = log_lines[-20:] if len(log_lines) > 20 else log_lines
                st.markdown("### 📜 最近操作日志")
                st.code("\n".join(last_20), language="markdown")
            else:
                st.info("日志文件尚未创建。")

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 4: 扫地僧 Agent
# ═══════════════════════════════════════════════════════════════════════════════

with tab4:
    st.subheader("💬 扫地僧 —— 知识库智能助手")
    st.caption("基于 Wiki 知识库回答舆情标注相关问题。引用来源均来自知识库页面。")

    # Render chat history
    for msg in st.session_state.agent_messages:
        with st.chat_message(msg["role"]):
            st.markdown(_convert_wikilinks(msg["content"]))
            if msg.get("citations"):
                _render_citations(msg["citations"])

    # Chat input
    if prompt := st.chat_input("问扫地僧任何问题...", key="agent_chat"):
        # Add user message
        st.session_state.agent_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get config and answer
        config = st.session_state.config
        if not config or not config.get("api_key"):
            with st.chat_message("assistant"):
                st.error("请先在侧边栏配置 API Key（加载知识库）。")
            st.session_state.agent_messages.append({
                "role": "assistant",
                "content": "⚠️ 请先在侧边栏配置 API Key（加载知识库）。",
                "citations": [],
            })
        else:
            with st.chat_message("assistant"):
                with st.spinner("扫地僧思考中..."):
                    # Build chat history for context (last 6 messages)
                    history = []
                    for m in st.session_state.agent_messages[-8:-1]:  # exclude the just-added user msg
                        if m["role"] in ("user", "assistant"):
                            history.append({"role": m["role"], "content": m["content"]})

                    from engine.agent import ask_agent
                    result = ask_agent(prompt, config, chat_history=history)

                if result.get("error"):
                    st.error(result["message"])
                    st.session_state.agent_messages.append({
                        "role": "assistant",
                        "content": f"❌ {result['message']}",
                        "citations": [],
                    })
                else:
                    st.markdown(_convert_wikilinks(result["answer"]))
                    if result.get("citations"):
                        _render_citations(result["citations"])
                    st.session_state.agent_messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "citations": result.get("citations", []),
                    })

    # Clear chat button
    if st.session_state.agent_messages:
        st.divider()
        if st.button("清空对话", key="clear_chat"):
            st.session_state.agent_messages = []
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 抓取逻辑
# ═══════════════════════════════════════════════════════════════════════════════

def _save_annotation_output(
    scraped_data: dict,
    annotation_result: dict,
    url: str = "",
) -> str | None:
    """Save annotation result to outputs/YYYY-MM-DD_platform_id_annotation.json."""
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
    """Exception-safe wrapper for ingestor.ingest()."""
    try:
        return ingest(scraped_data, annotation_result, url)
    except Exception as e:
        return {"action": "error", "case_file": None, "boundary_check": {}, "_ingest_error": str(e)}


def _clear_correction_widgets():
    """Remove stale correction widget state so new annotation values take effect."""
    for key in list(st.session_state.keys()):
        if key.startswith("corr_") or key.startswith("tab1_corr_") or key.startswith("tab2_corr_"):
            del st.session_state[key]


def do_scrape(url: str):
    with st.spinner(f"正在抓取 {url[:60]}..."):
        data = scrape(url)
        st.session_state.scraped_data = data
        st.session_state.annotation_result = None
        st.session_state.correction_result = None
        _clear_correction_widgets()
    return data

if scrape_btn and url_input.strip():
    do_scrape(url_input.strip())

if annotate_scraped_btn and url_input.strip():
    data = do_scrape(url_input.strip())
    if data and not data.get("_scrape_error"):
        config = st.session_state.config
        system_prompt, _ = build_system_prompt()
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
        st.session_state.correction_result = None
        _clear_correction_widgets()
        if result and not result.get("error"):
            _save_annotation_output(data, result, url_input.strip())
            st.session_state.ingest_result = _do_ingest(data, result, url_input.strip())

# 手动标注
if manual_annotate_btn and manual_content.strip():
    item = {
        "原文内容": manual_content.strip(),
        "来源平台": manual_platform,
        "发布者类型": manual_publisher or "未知",
        "互动数据": manual_engagement or "暂无",
        "发布时间": "",
        "原文链接": "",
    }
    # 评论区
    if manual_comments.strip():
        item["评论列表"] = [
            {"内容": line.strip(), "点赞": ""}
            for line in manual_comments.strip().split("\n")
            if line.strip()
        ][:10]

    st.session_state.scraped_data = item
    config = st.session_state.config
    system_prompt, _ = build_system_prompt()
    user_msg = format_user_message(item)
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
    st.session_state.correction_result = None
    _clear_correction_widgets()
    if result and not result.get("error"):
        _save_annotation_output(item, result)
        st.session_state.ingest_result = _do_ingest(item, result)

# ═══════════════════════════════════════════════════════════════════════════════
# 页脚
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.caption("舆情智能标注系统 | 基于 Wiki 知识库 + 案例驱动迭代 | DeepSeek / Claude / OpenAI 多 Provider 支持")
