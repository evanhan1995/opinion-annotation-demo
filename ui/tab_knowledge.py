# -*- coding: utf-8 -*-
"""Tab: 知识库 — merged Knowledge Base browser + 管理员AI dialog.

Layout:
  ┌──────────────┬─────────────────────────────┐
  │ Left (1/3)   │ Right top: 管理员AI chat     │
  │ Category nav │ Right bottom: page detail   │
  └──────────────┴─────────────────────────────┘
"""

import streamlit as st
from ui.shared import (
    _convert_wikilinks,
    _load_wiki_pages,
    _render_citations,
)
from ui.shared import (
    _convert_wikilinks,
    _load_wiki_pages,
    _render_citations,
)
from ui.theme import SEMANTIC_COLORS

KB_KEY = "kb_"


def _render_kb_nav(pages: list[dict]) -> str | None:
    """Render left-side category navigation. Returns selected page path."""
    selected = st.session_state.get("_selected_page")

    # Category definitions with sub-groups
    categories = [
        ("🔬 Concepts", "concepts", False),
        ("📄 Sources", "sources", False),
        ("📋 Cases", "cases", True),  # sub-grouped by platform
        ("👤 Authors", "authors", False),
        ("📅 日报", "reports_daily", False),
        ("📆 月报", "reports_monthly", False),
    ]

    from pathlib import Path

    for label, dirname, has_subgroups in categories:
        if dirname in ("reports_daily", "reports_monthly"):
            # Reports: scan wiki/reports/daily/ and wiki/reports/monthly/
            reports_dir = Path(__file__).resolve().parent.parent / "wiki" / "reports"
            if dirname == "reports_daily":
                scan_dir = reports_dir / "daily"
            else:
                scan_dir = reports_dir / "monthly"
            if scan_dir.exists():
                files = sorted(scan_dir.glob("*.md"), reverse=True)
                with st.expander(f"{label} ({len(files)})", expanded=False):
                    for f in files[:20]:
                        display = f.stem
                        btn_label = f"> {display}" if selected != f"reports/{dirname}/{f.name}" else f"**>> {display}**"
                        if st.button(btn_label, key=f"{KB_KEY}nav_reports_{dirname}_{f.name}", use_container_width=True):
                            st.session_state._selected_page = f"reports/{dirname}/{f.name}"
                            st.session_state._selected_page_content = f.read_text(encoding="utf-8")
                            st.rerun()
            continue

        if dirname == "cases":
            # Cases: sub-grouped by platform
            case_pages = [p for p in pages if p["dir"] == "cases"]
            if not case_pages:
                continue
            # Group by platform from frontmatter or filename
            platforms: dict[str, list] = {}
            for p in case_pages:
                # Extract platform from directory path
                pf = "其他"
                fp = p.get("_filepath", "")
                if "xiaohongshu" in fp:
                    pf = "小红书"
                elif "douyin" in fp:
                    pf = "抖音"
                elif "youtube" in fp:
                    pf = "YTB"
                elif "bilibili" in fp:
                    pf = "B站"
                elif "weibo" in fp:
                    pf = "微博"
                elif "wechat" in fp:
                    pf = "公众号"
                else:
                    # Legacy flat layout — try to guess from title
                    t = p.get("title", "").lower()
                    if "小红书" in t or "xiaohongshu" in t or "xhs" in t:
                        pf = "小红书"
                    elif "抖音" in t or "douyin" in t:
                        pf = "抖音"
                    elif "youtube" in t or "ytb" in t:
                        pf = "YTB"
                    elif "bilibili" in t or "b站" in t:
                        pf = "B站"
                    elif "微博" in t or "weibo" in t:
                        pf = "微博"
                platforms.setdefault(pf, []).append(p)

            with st.expander(f"📋 Cases ({len(case_pages)})", expanded=True):
                for pf_name in ["小红书", "抖音", "YTB", "B站", "微博", "公众号", "其他"]:
                    pf_cases = platforms.get(pf_name, [])
                    if not pf_cases:
                        continue
                    st.caption(f"▸ {pf_name} ({len(pf_cases)})")
                    for p in pf_cases[:30]:
                        is_sel = selected == p["path"]
                        btn_label = f"> {p['title'][:30]}" if not is_sel else f"**>> {p['title'][:30]}**"
                        if st.button(btn_label, key=f"{KB_KEY}nav_{p['path']}", use_container_width=True):
                            st.session_state._selected_page = p["path"]
                            st.rerun()
        else:
            # Regular flat categories
            group = [p for p in pages if p["dir"] == dirname]
            if not group:
                continue
            with st.expander(f"{label} ({len(group)})", expanded=False):
                for p in group:
                    is_sel = selected == p["path"]
                    btn_label = f"> {p['title'][:35]}" if not is_sel else f"**>> {p['title'][:35]}**"
                    if st.button(btn_label, key=f"{KB_KEY}nav_{p['path']}", use_container_width=True):
                        st.session_state._selected_page = p["path"]
                        st.rerun()

    return selected


def _get_report_html_path(selected: str) -> str:
    """Find or generate the HTML report file for a given report path.

    Returns path to .html file, or empty string if unavailable.
    """
    from pathlib import Path as _Path

    parts = selected.split("/")
    if len(parts) < 3:
        return ""
    report_type = parts[1]
    filename = parts[2]
    date_str = filename.replace(".md", "")

    # Check if HTML already exists on disk
    reports_dir = _Path(__file__).resolve().parent.parent / "wiki" / "reports"
    html_path = reports_dir / report_type / f"{date_str}.html"
    if html_path.exists():
        return str(html_path)

    # Generate on the fly
    try:
        from agents.daily_report import (
            _collect_report_data, generate_daily_html, generate_monthly_html,
        )
        if report_type == "monthly":
            data = _collect_report_data(month_str=date_str)
            return generate_monthly_html(data)
        else:
            data = _collect_report_data(date_str=date_str)
            return generate_daily_html(data)
    except Exception:
        return ""


def _render_report_download(selected: str):
    """Render HTML report download button for daily/monthly reports."""
    html_path = _get_report_html_path(selected)
    if not html_path:
        return

    from pathlib import Path as _Path
    try:
        html_bytes = _Path(html_path).read_bytes()
        parts = selected.split("/")
        filename = parts[2]
        date_str = filename.replace(".md", "")
        report_type = parts[1]
        download_name = f"舆情监测{'月报' if report_type == 'monthly' else '日报'}_{date_str}.html"

        st.download_button(
            label=f"📥 下载 HTML 报告 ({len(html_bytes)/1024/1024:.1f} MB)",
            data=html_bytes,
            file_name=download_name,
            mime="text/html",
            key=f"kb_dl_{selected}",
            use_container_width=True,
        )
    except Exception:
        pass  # silent — download is optional enhancement


def _render_page_detail(selected: str | None, pages: list[dict]):
    """Render the selected knowledge base page content."""
    if not selected:
        st.info("👈 从左侧选择一个页面来浏览")
        return

    page_paths = {p["path"]: p for p in pages}

    if selected.startswith("reports/"):
        # Report pages have pre-loaded content
        content = st.session_state.get("_selected_page_content", "")
        if content:
            # ── HTML download button ──
            _render_report_download(selected)

            # ── Preview mode toggle ──
            preview_mode = st.radio(
                "预览模式", ["Markdown", "HTML 预览"],
                horizontal=True,
                key=f"kb_preview_{selected}",
            )

            if preview_mode == "HTML 预览":
                html_path = _get_report_html_path(selected)
                if html_path:
                    from pathlib import Path
                    html_content = Path(html_path).read_text(encoding="utf-8")
                    st.caption(f"内嵌预览 · 文件大小: {len(html_content)/1024/1024:.1f} MB")
                    st.components.v1.html(html_content, height=2400, scrolling=True)
                else:
                    st.warning("HTML 报告不可用，请先通过侧边栏生成今日报告。")
            else:
                st.divider()
                st.markdown(content)
        else:
            st.info("报告内容不可用")
        return

    if selected not in page_paths:
        st.info("页面不存在")
        return

    page_data = page_paths[selected]
    md_content = _convert_wikilinks(page_data.get("content", ""))

    # Show status badge for case pages
    if page_data.get("type") == "case" or page_data.get("dir") == "cases":
        status = page_data.get("status", "")
        if status:
            status_colors = SEMANTIC_COLORS["kb_status"]
            color = status_colors.get(status, "#6c757d")
            st.markdown(
                f"<span style='background:{color};color:white;padding:2px 10px;border-radius:10px;"
                f"font-size:0.9em;margin-right:8px;'>状态: {status}</span>",
                unsafe_allow_html=True,
            )
            st.divider()

    st.markdown(md_content)


def _get_kb_password() -> str:
    """Read knowledge base password from secrets/env/config."""
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
        from engine.annotate import load_config
        return load_config().get("kb_password", "")
    except Exception:
        return ""


def render_tab_knowledge():
    """Render the merged knowledge base + admin AI tab."""
    st.subheader("📚 知识库")
    st.caption("浏览知识库内容 + 管理员AI智能问答")

    pages = _load_wiki_pages()
    has_password = bool(_get_kb_password())

    # Password gate
    if has_password and not st.session_state.get("kb_authenticated"):
        st.info("🔒 知识库内容受密码保护。请在下方输入密码解锁。")
        pw_input = st.text_input("知识库密码", type="password", placeholder="输入密码查看内容", key=f"{KB_KEY}pw_input")
        if st.button("解锁知识库", key=f"{KB_KEY}unlock", use_container_width=True):
            if pw_input == _get_kb_password():
                st.session_state.kb_authenticated = True
                st.rerun()
            else:
                st.error("密码错误，请重试")
        return

    # ── Main layout ───────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 3])

    with left_col:
        st.markdown("**分类导航**")
        selected = _render_kb_nav(pages)

        st.divider()
        if has_password and st.button("🔒 锁定知识库", key=f"{KB_KEY}lock", use_container_width=True):
            st.session_state.kb_authenticated = False
            st.rerun()
        if st.button("🔄 刷新", key=f"{KB_KEY}refresh", use_container_width=True):
            st.rerun()

    with right_col:
        # ── Top: 管理员AI dialog ──────────────────────────────────────
        with st.container():
            st.markdown("**🤖 管理员AI**")
            st.caption("基于知识库回答舆情标注相关问题。")

            for msg in st.session_state.get("agent_messages", []):
                with st.chat_message(msg["role"]):
                    st.markdown(_convert_wikilinks(msg["content"]))
                    if msg.get("citations"):
                        _render_citations(msg["citations"])

            if prompt := st.chat_input("向管理员AI提问...", key=f"{KB_KEY}chat_input"):
                st.session_state.agent_messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                config = st.session_state.config
                if not config or not config.get("api_key"):
                    with st.chat_message("assistant"):
                        st.error("请先在侧边栏配置 API Key（加载知识库）。")
                    st.session_state.agent_messages.append({
                        "role": "assistant",
                        "content": "请先在侧边栏配置 API Key。",
                        "citations": [],
                    })
                else:
                    with st.chat_message("assistant"):
                        with st.spinner("管理员AI思考中..."):
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

            if st.session_state.get("agent_messages"):
                if st.button("清空对话", key=f"{KB_KEY}clear_chat"):
                    st.session_state.agent_messages = []
                    st.rerun()

        # ── Bottom: Page detail ───────────────────────────────────────
        st.divider()
        st.markdown("**📄 知识库详情**")
        _render_page_detail(selected, pages)
