# -*- coding: utf-8 -*-
"""Tab 4: Case Disposition — view and update case statuses."""

import streamlit as st
from datetime import datetime
from ui.theme import spacer


def _load_cases(status_filter: str = "全部", severity_filter: list[str] | None = None):
    """Load case metadata via Curator API (PRD: single legal read path)."""
    if severity_filter is None:
        severity_filter = ["P0", "P1", "P2", "P3"]
    from agents.curator import query_cases
    filters = {}
    if status_filter != "全部":
        filters["status"] = status_filter
    cases = query_cases(filters)
    # Apply severity filter (curator doesn't support list filter yet, do client-side)
    cases = [c for c in cases if c["severity"] in severity_filter]
    cases.sort(key=lambda c: c.get("ingested_at", ""), reverse=True)
    return cases


def render_tab4():
    """Render the case disposition tab."""
    st.subheader("📋 案例处置")

    # ── 超24小时未处理警告 (5c) ──────────────────────────────────────
    from datetime import datetime as _dt, timedelta as _td
    all_cases = _load_cases("全部", ["P0", "P1", "P2", "P3"])
    overdue_cases = []
    now = _dt.now()
    for c in all_cases:
        if c["status"] == "待跟进" and c.get("assigned_date"):
            try:
                assigned = _dt.strptime(c["assigned_date"][:10], "%Y-%m-%d")
                if (now - assigned).total_seconds() > 86400:
                    overdue_cases.append(c)
            except ValueError:
                pass
    if overdue_cases:
        st.error(f"⚠️ 你有 {len(overdue_cases)} 条舆情超24小时未处理")

    # ── Dashboard cards ───────────────────────────────────────────────
    total_pending = sum(1 for c in all_cases if c["status"] == "待跟进")
    total_in_progress = sum(1 for c in all_cases if c["status"] == "处理中")
    total_overdue = len(overdue_cases)
    total_resolved = sum(1 for c in all_cases if c["status"] == "已处理")
    total_ignored = sum(1 for c in all_cases if c["status"] == "忽略")
    total_abandoned = sum(1 for c in all_cases if c["status"] == "已放弃")

    dash_col1, dash_col2, dash_col3 = st.columns(3)
    with dash_col1:
        if st.button(f"📥 待处理\n\n**{total_pending}**", key="dash_pending",
                     use_container_width=True, help="点击查看待处理案例"):
            st.session_state["disp_status_filter"] = "待跟进"
            st.rerun()
    with dash_col2:
        if st.button(f"🔄 跟进中\n\n**{total_in_progress}**", key="dash_in_progress",
                     use_container_width=True, help="点击查看跟进中案例"):
            st.session_state["disp_status_filter"] = "处理中"
            st.rerun()
    with dash_col3:
        btn_label = f"🚨 已超时\n\n**{total_overdue}**"
        if st.button(btn_label, key="dash_overdue",
                     use_container_width=True, help="点击查看超24小时未处理案例",
                     type="secondary" if total_overdue == 0 else "primary"):
            st.session_state["disp_status_filter"] = "待跟进"
            st.session_state["_show_overdue_only"] = True
            st.rerun()

    dash_col4, dash_col5, dash_col6 = st.columns(3)
    with dash_col4:
        if st.button(f"✅ 已处理\n\n**{total_resolved}**", key="dash_resolved",
                     use_container_width=True, help="点击查看已处理案例"):
            st.session_state["disp_status_filter"] = "已处理"
            st.rerun()
    with dash_col5:
        if st.button(f"🚫 已忽略\n\n**{total_ignored}**", key="dash_ignored",
                     use_container_width=True, help="点击查看已忽略案例"):
            st.session_state["disp_status_filter"] = "忽略"
            st.rerun()
    with dash_col6:
        if st.button(f"❌ 已放弃\n\n**{total_abandoned}**", key="dash_abandoned",
                     use_container_width=True, help="点击查看已放弃案例"):
            st.session_state["disp_status_filter"] = "已放弃"
            st.rerun()

    # ── Filters ───────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        status_filter = st.selectbox(
            "按状态筛选", ["全部", "待跟进", "处理中", "已处理", "已放弃", "忽略"],
            key="disp_status_filter",
        )
    with col_b:
        sev_filter = st.multiselect(
            "按严重度筛选", ["P0", "P1", "P2", "P3"],
            default=["P0", "P1", "P2", "P3"],
            key="disp_sev_filter",
        )
    with col_c:
        spacer()  # spacer

    # Empty selection = show all severities
    if not sev_filter:
        sev_filter = ["P0", "P1", "P2", "P3"]
    cases = _load_cases(status_filter, sev_filter)

    # Apply overdue-only filter
    if st.session_state.pop("_show_overdue_only", False):
        cases = [c for c in cases if c in overdue_cases]
    st.caption(f"共 {len(cases)} 个案例")

    if not cases:
        st.info("暂无符合条件的案例")
        return

    for case in cases:
        cid = case["case_id"]
        assigned_info = f" | 指派: {case.get('assigned_date', '无')}" if case.get("assigned_date") else ""
        with st.expander(
            f"[{case['severity']}] {case['title'][:50]} — {case['status']} ({case['platform']}){assigned_info}",
            expanded=case["severity"] in ("P0", "P1"),
        ):
            st.markdown(
                f"**平台**: {case['platform']} | **严重度**: {case['severity']} | "
                f"**当前状态**: {case['status']}"
            )
            if case.get("url"):
                st.caption(case["url"][:100])
            if case.get("assigned_date"):
                st.caption(f"📅 被指派日期: {case['assigned_date']}")

            cur_idx = ["待跟进", "处理中", "已处理", "已放弃", "忽略"].index(case["status"]) \
                if case["status"] in ["待跟进", "处理中", "已处理", "已放弃", "忽略"] else 0

            new_status = st.selectbox(
                "更新状态",
                ["待跟进", "处理中", "已处理", "已放弃", "忽略"],
                index=cur_idx,
                key=f"status_sel_{cid}",
            )
            notes = st.text_input("备注", value=case.get("notes", ""),
                                  key=f"notes_{cid}", placeholder="可选：处置备注")

            if st.button("更新状态", key=f"update_btn_{cid}"):
                if new_status != case["status"]:
                    try:
                        from agents.orchestrator import handle_status_transition
                        result = handle_status_transition(
                            cid, case["status"], new_status, notes, operator="UI"
                        )
                        if result.get("success"):
                            st.success(f"已更新: {case['status']} → {new_status}")
                            st.rerun()
                        else:
                            st.error(result.get("error", "更新失败"))
                    except Exception as e:
                        st.error(f"更新失败: {e}")
                else:
                    st.info("状态未变更")
