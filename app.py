# -*- coding: utf-8 -*-
"""舆情智能标注系统 —— Web 界面

使用方法:
    streamlit run app.py
    然后在浏览器中打开 http://localhost:8501
"""

import sys
from pathlib import Path

# 路径设置（确保能 import engine 模块）
PROJECT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = PROJECT_DIR / "engine"
OUTPUT_DIR = PROJECT_DIR / "outputs"
sys.path.insert(0, str(PROJECT_DIR))

import streamlit as st
from engine.annotate import load_config
from engine.scraper import SCRAPERS

from ui.shared import (
    _convert_wikilinks,
    _load_wiki_pages,
    _render_citations,
)
from ui.sidebar import render_sidebar
from ui.tab1_manual import render_tab1
from ui.tab2_url import render_tab2
from ui.tab5_demo import render_tab5

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
        1. **操作演示** → 切换到「🎬 操作演示」，查看离线模拟全流程
        2. **URL 抓取** → 切换到「🔗 URL 抓取」，粘贴 YouTube / 小红书链接
        3. **查看知识库** → 切换到「📚 知识库」浏览案例和作者
        4. **手工录入** → 切换到「📝 手工录入」手动填写内容并保存
        5. **扫地僧** → 切换到「💬 扫地僧」向知识库提问
        """)
        if st.button("知道了，开始使用", key="dismiss_guide"):
            st.session_state.demo_guide_shown = True
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════════════════════════════════════

render_sidebar(_patrol_pending)

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 布局
# ═══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 手工录入", "🔗 URL 抓取", "📚 知识库", "💬 扫地僧", "🎬 操作演示"
])

with tab1:
    render_tab1()

with tab2:
    render_tab2(_pending_annotate_url, _pending_batch_urls)

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 3: 知识库浏览器
# ═══════════════════════════════════════════════════════════════════════════════

def _get_kb_password() -> str:
    """Read knowledge base password from secrets/env/config (never from source code)."""
    try:
        pw = st.secrets.get("KB_PASSWORD", "")
        if pw:
            return pw
    except Exception:
        pass
    import os
    pw = os.getenv("KB_PASSWORD", "")
    if pw:
        return pw
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
        st.caption("📜 操作日志")
        if st.button("🔄 刷新", use_container_width=True, key="refresh_wiki"):
            st.rerun()

    with col_content:
        has_password = bool(_get_kb_password())
        if has_password and not st.session_state.kb_authenticated:
            st.info("🔒 知识库内容受密码保护。请在下方输入密码解锁。")
            _kb_password_form()
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

    for msg in st.session_state.agent_messages:
        with st.chat_message(msg["role"]):
            st.markdown(_convert_wikilinks(msg["content"]))
            if msg.get("citations"):
                _render_citations(msg["citations"])

    if prompt := st.chat_input("问扫地僧任何问题...", key="agent_chat"):
        st.session_state.agent_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

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
                    history = []
                    for m in st.session_state.agent_messages[-8:-1]:
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

    if st.session_state.agent_messages:
        st.divider()
        if st.button("清空对话", key="clear_chat"):
            st.session_state.agent_messages = []
            st.rerun()

with tab5:
    render_tab5()

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
