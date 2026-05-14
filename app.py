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
from engine.scraper import scrape, SCRAPERS, _detect_platform, _extract_content_id, PLATFORM_ABBREV, fetch_youtube_subtitles
from engine.annotate import (
    build_system_prompt,
    load_config,
    format_user_message,
    annotate_one,
    annotate_one_stream,
    CATEGORY_OPTIONS,
    find_similar_cases,
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
    ("demo_guide_shown", False),
    ("kb_authenticated", False),
    ("batch_results", None),
    ("_result_source", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# Snap deferred annotation requests (cleared old result on previous run, now do actual work)
_pending_annotate_url = st.session_state.pop("_annotate_url", None)
_pending_batch_urls = st.session_state.pop("_batch_urls", None)
_patrol_pending = st.session_state.pop("_patrol_pending", False)

# Demo guide: show once per session
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
# 侧边栏：系统状态
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.subheader("⚙️ 系统")

    # Auto-load KB on first visit
    if st.session_state.config is None:
        config = load_config()
        _, kb_stats = build_system_prompt()
        st.session_state.config = config
        st.session_state.system_prompt_loaded = True
        st.session_state.kb_stats = kb_stats

    if st.button("🔄 刷新知识库", use_container_width=True):
        with st.spinner("加载中..."):
            config = load_config()
            _, kb_stats = build_system_prompt()
            st.session_state.config = config
            st.session_state.system_prompt_loaded = True
            st.session_state.kb_stats = kb_stats

    kb = st.session_state.kb_stats
    if kb:
        loaded = sum(1 for v in kb["layers"].values() if v["status"] == "loaded")
        st.caption(f"知识库: {loaded}/{len(kb['layers'])} 页 | 模型: {st.session_state.config.get('model', '?')}")
    api_key = (st.session_state.config or {}).get("api_key", "")
    st.caption(f"API Key: {'✅' if api_key else '⚠️ 未配置'}")

    # Dashboard (always visible, compact)
    st.divider()
    try:
        cases_dir = PROJECT_DIR / "wiki" / "cases"
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
        c1, c2, c3 = st.columns(3)
        c1.metric("案例", total)
        c2.metric("P0/P1", sev_count.get("P0", 0) + sev_count.get("P1", 0))
        c3.metric("平台", len(plat_count))
        st.caption(f"P0:{sev_count['P0']} P1:{sev_count['P1']} P2:{sev_count['P2']} P3:{sev_count['P3']}" +
                   (f"  |  " + " ".join(f"{k}:{v}" for k, v in sorted(plat_count.items(), key=lambda x: -x[1])[:4]) if plat_count else ""))
    except Exception:
        st.caption("仪表盘加载失败")

    # 监控 & 工具
    st.divider()
    with st.expander("📡 巡检 & 登录", expanded=bool(_patrol_pending)):
        patrol_urls_file = ENGINE_DIR / "monitored_urls.json"
        if patrol_urls_file.exists():
            import json as _json
            patrol_urls = _json.loads(patrol_urls_file.read_text(encoding="utf-8"))
            st.caption(f"监控 {len(patrol_urls)} 个链接")
            if st.button("立即巡检", use_container_width=True, key="patrol_btn"):
                st.session_state._patrol_pending = True
                st.rerun()
            # Execute patrol if pending
            if _patrol_pending:
                config = st.session_state.config
                system_prompt = build_system_prompt()[0]
                results = []
                p0p1 = 0
                status = st.empty()
                for u in patrol_urls:
                    status.info(f"巡检中: {u[:60]}...")
                    try:
                        data = scrape(u)
                        if data and not data.get("_scrape_error"):
                            user_msg = format_user_message(data)
                            result = None
                            for event in annotate_one_stream(user_msg, system_prompt, config):
                                if event["type"] == "result":
                                    result = event["data"]
                            if result and not result.get("error"):
                                sev = result.get("严重度评级", "")
                                if sev in ("P0", "P1"):
                                    p0p1 += 1
                                ir = _do_ingest(data, result, u)
                                results.append({"url": u, "severity": sev, "action": result.get("分流建议", "?"), "summary": result.get("摘要", "")[:60]})
                    except Exception:
                        pass
                status.empty()
                st.session_state._patrol_result = {"ok": len(results), "total": len(patrol_urls), "p0p1": p0p1, "items": results}
                st.session_state._needs_rerun = True
            # Show last patrol result
            if st.session_state.get("_patrol_result"):
                pr = st.session_state._patrol_result
                ok = pr["ok"]; total = pr["total"]; p0p1 = pr["p0p1"]
                st.caption(f"上次巡检: {ok}/{total} 成功, P0/P1: {p0p1}")
                if p0p1 > 0:
                    st.error(f"⚠️ {p0p1} 条高优案例需关注")
                    for item in pr.get("items", []):
                        if item.get("severity") in ("P0", "P1"):
                            st.markdown(f"- **{item['severity']}** {item['summary'][:50]}...")
        else:
            st.caption("无监控配置")

        st.divider()
        st.caption("小红书登录状态")
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
                        st.error("Cookie 已过期")
                    elif days_left <= 1:
                        st.warning(f"Cookie 即将过期 ({days_left}天)")
                    else:
                        st.caption(f"Cookie 有效 (剩余 {days_left} 天)")
        except Exception:
            pass
        if st.button("刷新小红书登录", use_container_width=True, key="sidebar_xhs_login"):
            from engine.xhs_fetcher import bootstrap_cookies
            with st.spinner("正在打开浏览器..."):
                if bootstrap_cookies(force=True):
                    st.success("登录成功！")
                else:
                    st.error("登录失败")

# ═══════════════════════════════════════════════════════════════════════════════
# Demo 数据
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
    dir_order = ["concepts", "entities", "sources", "syntheses", "cases", "authors"]

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
        with st.expander(f"📊 社媒数据 — {social.get('作者', '?')}", expanded=False, key=f"{key_prefix}social_card"):
            c0, c1, c2, c3, c4, c5 = st.columns(6)
            views = social.get("播放量")
            c0.metric("平台", platform)
            c1.metric("播放量", f"{views:,}" if views else "—",
                      help="[估算]" if social.get("_播放量估算") else None)
            c2.metric("点赞", f"{social.get('点赞', 0):,}" if social.get('点赞') else "—")
            c3.metric("评论", f"{social.get('评论', 0):,}" if social.get('评论') else "—")
            c4.metric("粉丝", f"{social.get('粉丝', 0):,}" if social.get('粉丝') else "—")
            c5.metric("国家", social.get("国家") or "—")
            st.caption(f"🕐 发布时间: {pub_time}" + (f" | ⏱ 时长: {social.get('时长')}" if social.get('时长') else ""))
            if social.get("作者主页"):
                for hp in social["作者主页"]:
                    if hp:
                        st.caption(f"🔗 {hp}")

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
        st.markdown(f"**📝 简介**: {summary}")

    # -------- YouTube AI 深度分析（仅 YouTube 平台）--------
    if scraped and scraped.get("来源平台") == "YouTube":
        yt_col1, yt_col2 = st.columns([1, 3])
        with yt_col1:
            if st.button("🎬 YouTube AI 视频内容分析", key=f"{key_prefix}yt_deep_analysis"):
                st.session_state[f"{key_prefix}_yt_analyze"] = True
                st.rerun()
        with yt_col2:
            if "字幕" not in scraped.get("原文内容", ""):
                if st.button("📥 下载字幕 TXT", key=f"{key_prefix}sub_download"):
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
                        st.success("🎬 AI 视频内容分析")
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
            with st.expander(f"🔍 近似舆情 ({len(similar)} 个相似案例)", expanded=False, key=f"{key_prefix}similar_cases"):
                for s in similar:
                    cid = s["filename"].replace(".md", "")
                    st.markdown(
                        f"- [[cases/{cid}|{s['filename'].replace('.md','')}]] "
                        f"**{s['severity']}** | 命中 {s['hits']} tag | {s['title'][:50]}"
                    )
                    if st.button(f"📖 查看 {s['filename']}", key=f"{key_prefix}view_{s['filename']}"):
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
    # 标注历史回溯
    # ═══════════════════════════════════════════════════════════════════
    url_for_history = st.session_state.get("scraped_data", {}).get("原文链接", "")
    if url_for_history:
        from engine.annotate import find_annotation_history, diff_annotations
        history = find_annotation_history(url_for_history)
        if len(history) >= 2:
            with st.expander(f"📜 标注历史 ({len(history)} 次记录)", expanded=False, key=f"{key_prefix}history_expander"):
                # Timeline: newest first
                for h_idx, h in enumerate(history):
                    a = h["annotation"]
                    sev = a.get("严重度评级", "?")
                    act = a.get("分流建议", "?")
                    sent = a.get("情感分析", {}).get("整体情感", "?")
                    st.caption(f"**{h['date']}** — {sev} | {act} | {sent}")
                    # Diff with previous
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
            # Boundary suggestions (draft-PR style)
            suggestions = ir.get("boundary_suggestions", [])
            if suggestions:
                with st.expander("📝 建议更新知识库概念页（Draft PR）", expanded=False):
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
# Helper functions (must be defined before tabs — called in deferred annotation blocks)
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


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 手工录入", "🔗 URL 抓取", "📚 知识库", "💬 扫地僧", "🎬 操作演示"
])

with tab1:
    st.caption("适用于小红书/YTB之外的平台内容，或无法自动抓取的内容。所有字段人工填写。")

    # --- txt upload → AI summary ---
    uploaded_file = st.file_uploader("📎 上传 txt 文件（AI 自动总结）", type=["txt"], key="manual_upload")
    ai_summary_btn = st.button("🤖 AI 总结上传内容", disabled=not bool(uploaded_file), key="ai_summary_btn",
                               help="读取上传的 txt 内容，AI 生成简介摘要")

    if ai_summary_btn and uploaded_file:
        try:
            txt_content = uploaded_file.read().decode("utf-8")
            st.session_state.manual_content = txt_content[:5000]
            # Generate summary via LLM
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

with tab2:
    st.info("URL 抓取需要本地浏览器环境，在线 Demo 不可用。支持 YouTube 和小红书链接。")
    url_input = st.text_input(
        "粘贴舆情链接",
        placeholder="https://www.xiaohongshu.com/explore/... 或 https://www.youtube.com/watch?v=...",
        key="url_input",
    )
    # URL validation: only YouTube and 小红书 are supported
    url_valid = True
    url_platform = ""
    if url_input.strip():
        url_platform = _detect_platform(url_input.strip())
        if url_platform not in ("YouTube", "小红书"):
            url_valid = False
            st.warning(f"暂不支持「{url_platform}」平台。目前仅支持 YouTube 和小红书链接。")

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
            # Store last single result for _render_annotation_result compatibility
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
# Tab 3: 知识库浏览器
# ═══════════════════════════════════════════════════════════════════════════════

def _get_kb_password() -> str:
    """Read knowledge base password from secrets/env/config (never from source code)."""
    # 1. Streamlit Cloud Secrets
    try:
        pw = st.secrets.get("KB_PASSWORD", "")
        if pw:
            return pw
    except Exception:
        pass
    # 2. Environment variable
    import os
    pw = os.getenv("KB_PASSWORD", "")
    if pw:
        return pw
    # 3. Local config.json (gitignored)
    try:
        config = load_config()
        return config.get("kb_password", "")
    except Exception:
        return ""


def _kb_password_form():
    """Render a compact password input that unlocks the knowledge base."""
    pw = st.text_input("知识库密码", type="password", placeholder="输入密码查看内容",
                       key="kb_pw_input")
    if st.button("解锁知识库", key="kb_unlock_btn", use_container_width=True):
        if pw == _get_kb_password():
            st.session_state.kb_authenticated = True
            st.rerun()
        else:
            st.error("密码错误，请重试")


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
            "authors": ("👤 Authors", False),
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
        # Logs are also protected
        st.caption("📜 操作日志")
        if st.button("🔄 刷新", use_container_width=True, key="refresh_wiki"):
            st.rerun()

    with col_content:
        # --- Password gate ---
        has_password = bool(_get_kb_password())
        if has_password and not st.session_state.kb_authenticated:
            st.info("🔒 知识库内容受密码保护。请在下方输入密码解锁。")
            _kb_password_form()
            # Show log only on default view, protected
            selected = st.session_state.get("_selected_page")
            if not selected:
                st.markdown("### 📜 最近操作日志")
                st.caption("(输入密码后可查看完整内容)")
        else:
            selected = st.session_state.get("_selected_page")
            page_paths = {p["path"]: p for p in pages}

            if selected and selected in page_paths:
                page_data = page_paths[selected]
                md_content = _convert_wikilinks(page_data["content"])
                st.markdown(md_content)
                # Lock button to re-lock when leaving
                if has_password:
                    st.divider()
                    if st.button("🔒 锁定知识库", key="kb_lock_btn"):
                        st.session_state.kb_authenticated = False
                        st.rerun()
            else:
                st.info("👈 从左侧选择一个页面来浏览")
                log_path = PROJECT_DIR / "wiki" / "log.md"
                if log_path.exists():
                    log_lines = log_path.read_text(encoding="utf-8").strip().split("\n")
                    last_20 = log_lines[-20:] if len(log_lines) > 20 else log_lines
                    if has_password and st.session_state.kb_authenticated:
                        st.markdown("### 📜 最近操作日志")
                        st.code("\n".join(last_20), language="markdown")
                    elif not has_password:
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
# Tab 5: 操作演示 (完全模拟，不调API，不写知识库)
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

with tab5:
    st.subheader("🎬 操作演示")
    st.caption("模拟完整 URL 抓取→AI 标注→纠偏流程。全程离线，不调用 API，不写入知识库。")

    demo_step = st.session_state.get("demo_step", 0)

    # Step 0: Input URL
    if demo_step == 0:
        st.info("**Step 1/4**: 输入舆情链接")
        demo_url = st.text_input("粘贴舆情链接", value=DEMO_URL, key="demo_url")
        if st.button("抓取并标注 →", type="primary", use_container_width=True, key="demo_start"):
            st.session_state.demo_step = 1
            st.rerun()

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
            st.rerun()

        st.caption("⚠️ 以上为模拟数据，不会写入知识库。实际操作请在「URL 抓取」标签页进行。")


# ═══════════════════════════════════════════════════════════════════════════════
# 抓取逻辑
if scrape_btn and url_input.strip():
    do_scrape(url_input.strip())

if annotate_scraped_btn and url_input.strip():
    st.session_state.annotation_result = None
    st.session_state.ingest_result = None
    st.session_state.correction_result = None
    st.session_state._annotate_url = url_input.strip()
    st.rerun()

# 批量标注
if batch_btn and batch_urls_text.strip():
    urls = [u.strip() for u in batch_urls_text.split("\n") if u.strip()]
    if len(urls) >= 2:
        st.session_state.annotation_result = None
        st.session_state.ingest_result = None
        st.session_state.correction_result = None
        st.session_state.batch_results = None
        st.session_state._batch_urls = urls
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# 显式重跑：确保标注完成后页面刷新到最新结果
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state.get("_needs_rerun"):
    st.session_state._needs_rerun = False
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# 页脚
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.caption("舆情智能标注系统 | 基于 Wiki 知识库 + 案例驱动迭代 | DeepSeek / Claude / OpenAI 多 Provider 支持")
