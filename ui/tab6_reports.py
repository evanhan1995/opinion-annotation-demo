# -*- coding: utf-8 -*-
"""Tab 6: Reports Viewer — daily and monthly report browsing."""

import logging
import streamlit as st
from pathlib import Path

_log = logging.getLogger("yuqing")

WIKI_DIR = Path(__file__).resolve().parent.parent / "wiki"
REPORTS_DAILY = WIKI_DIR / "reports" / "daily"
REPORTS_MONTHLY = WIKI_DIR / "reports" / "monthly"


def _read_report_markdown(report_type: str, date_str: str, md_path: Path) -> str:
    """优先读 FinalReport 缓存（.report.json），缺则回退 .md（兼容历史报告）。

    区分两种情况（沿用任务2「静默吞错修复」标准）：
      - 缓存缺失或为空（确实无缓存内容）→ 正常回退 .md，不记日志。
      - 读取缓存抛异常（读取失败）→ logging.exception 记录完整堆栈后回退 .md。
    """
    try:
        from engine.report_model import load_final_report
        fr = load_final_report(report_type, date_str)
        if fr is not None and fr.markdown:
            from shared.report_renderers import render_web
            return render_web(fr)
    except Exception as e:
        _log.exception("读取报告缓存失败，回退 .md: type=%s date=%s: %s", report_type, date_str, e)
    return md_path.read_text(encoding="utf-8")


def render_tab6():
    """Render the reports viewer tab."""
    st.subheader("📊 报告查看")

    report_type = st.radio(
        "报告类型", ["📅 日报", "📆 月报"],
        horizontal=True, key="report_type_radio",
    )

    if report_type == "📅 日报":
        _render_daily_reports()
    else:
        _render_monthly_reports()


def _render_daily_reports():
    if not REPORTS_DAILY.exists():
        st.info("暂无日报文件")
        return

    files = sorted(REPORTS_DAILY.glob("*.md"), reverse=True)
    dates = [f.stem for f in files]

    if not dates:
        st.info("暂无日报文件")
        return

    selected = st.selectbox("选择日期", dates, key="daily_date_select")
    if selected:
        content = _read_report_markdown("daily", selected, REPORTS_DAILY / f"{selected}.md")
        st.markdown(content)

    # Show post-rerun message (st.success is cleared by st.rerun)
    _gen_daily_msg = st.session_state.pop("_gen_daily_msg", "")
    if _gen_daily_msg:
        if "失败" in _gen_daily_msg:
            st.error(_gen_daily_msg)
        else:
            st.success(f"日报已保存: {_gen_daily_msg}")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 生成今日日报", key="gen_daily_btn", use_container_width=True):
            with st.spinner("生成日报中..."):
                from agents.orchestrator import run_daily_report
                st.session_state._gen_daily_msg = run_daily_report()
            st.rerun()


def _render_monthly_reports():
    if not REPORTS_MONTHLY.exists():
        st.info("暂无月报文件")
        return

    files = sorted(REPORTS_MONTHLY.glob("*.md"), reverse=True)
    months = [f.stem for f in files]

    if not months:
        st.info("暂无月报文件")
        return

    selected = st.selectbox("选择月份", months, key="monthly_date_select")
    if selected:
        content = _read_report_markdown("monthly", selected, REPORTS_MONTHLY / f"{selected}.md")
        st.markdown(content)

    # Show post-rerun message
    _gen_monthly_msg = st.session_state.pop("_gen_monthly_msg", "")
    if _gen_monthly_msg:
        if "失败" in _gen_monthly_msg:
            st.error(_gen_monthly_msg)
        else:
            st.success(f"月报已保存: {_gen_monthly_msg}")

    if st.button("🔄 生成本月月报", key="gen_monthly_btn", use_container_width=True):
        with st.spinner("生成月报中..."):
            from agents.orchestrator import run_monthly_report
            st.session_state._gen_monthly_msg = run_monthly_report()
        st.rerun()
