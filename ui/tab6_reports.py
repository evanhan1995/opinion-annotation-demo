# -*- coding: utf-8 -*-
"""Tab 6: Reports Viewer — daily and monthly report browsing."""

import streamlit as st
from pathlib import Path

WIKI_DIR = Path(__file__).resolve().parent.parent / "wiki"
REPORTS_DAILY = WIKI_DIR / "reports" / "daily"
REPORTS_MONTHLY = WIKI_DIR / "reports" / "monthly"


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
        content = (REPORTS_DAILY / f"{selected}.md").read_text(encoding="utf-8")
        st.markdown(content)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 生成今日日报", key="gen_daily_btn", use_container_width=True):
            with st.spinner("生成日报中..."):
                from agents.orchestrator import run_daily_report
                path = run_daily_report()
                st.success(f"日报已保存: {path}")
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
        content = (REPORTS_MONTHLY / f"{selected}.md").read_text(encoding="utf-8")
        st.markdown(content)

    if st.button("🔄 生成本月月报", key="gen_monthly_btn", use_container_width=True):
        with st.spinner("生成月报中..."):
            from agents.orchestrator import run_monthly_report
            path = run_monthly_report()
            st.success(f"月报已保存: {path}")
            st.rerun()
