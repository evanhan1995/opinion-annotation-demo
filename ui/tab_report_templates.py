# -*- coding: utf-8 -*-
"""报告模板管理 Tab：上传 Markdown 案例学习模板 + 预览/编辑/调序 + 设为激活。"""
import re

import streamlit as st

from engine.report_model import (
    default_template, save_template, list_templates, get_active_template,
    set_active_template, ReportTemplate, TemplateModule,
)
from engine.report_template_learner import learn_template_from_examples


def render_tab_report_templates():
    st.subheader("📐 报告模板管理")

    label = st.radio("模板类型", ["日报", "月报"], horizontal=True, key="tpl_type")
    rt_key = "daily" if label == "日报" else "monthly"

    _render_learn_section(rt_key)
    st.divider()
    _render_template_list(rt_key)
    st.divider()
    _render_editor(rt_key)


# ── 1. 上传案例学习 ─────────────────────────────────────────────────────

def _render_learn_section(rt_key: str):
    st.markdown("### 1. 上传历史报告案例，学习模板")
    st.caption("上传多个 .md 历史报告，系统学习其结构（数字自动脱敏），产出模板草稿。")

    uploaded = st.file_uploader(
        "上传 .md 案例", type=["md"], accept_multiple_files=True,
        key=f"tpl_upload_{rt_key}",
    )

    if st.button("🧠 学习模板", key=f"tpl_learn_{rt_key}", use_container_width=True):
        if not uploaded:
            st.session_state[f"tpl_msg_{rt_key}"] = "请先上传至少一个 .md 案例"
            return
        try:
            contents = [f.getvalue().decode("utf-8") for f in uploaded]
            with st.spinner("解析案例结构并归纳模板..."):
                tpl = learn_template_from_examples(contents, rt_key)
            st.session_state[f"tpl_draft_{rt_key}"] = tpl
            st.session_state[f"tpl_msg_{rt_key}"] = f"学习完成，识别 {len(tpl.modules)} 个模块"
        except Exception as e:
            st.session_state[f"tpl_msg_{rt_key}"] = f"学习失败: {e}"

    msg = st.session_state.pop(f"tpl_msg_{rt_key}", "")
    if msg:
        st.info(msg)

    draft = st.session_state.get(f"tpl_draft_{rt_key}")
    if not draft:
        return

    st.markdown("**模板草稿预览**")
    _render_module_table(draft.modules)

    c1, c2 = st.columns([2, 1])
    with c1:
        name = st.text_input("模板名称", value=draft.name, key=f"tpl_draft_name_{rt_key}")
    with c2:
        if st.button("💾 保存为模板", key=f"tpl_save_draft_{rt_key}", use_container_width=True):
            tid = "custom-" + re.sub(r"[^\w一-鿿-]+", "-", name.strip()) or f"custom-{rt_key}"
            draft.name = name.strip() or draft.name
            draft.template_id = tid
            draft.version = 1
            save_template(draft)
            st.session_state[f"tpl_msg_{rt_key}"] = f"已保存模板：{draft.name}（{tid}）"
            st.session_state[f"tpl_draft_{rt_key}"] = None
            st.rerun()


# ── 2. 模板列表 + 激活 ──────────────────────────────────────────────────

def _render_template_list(rt_key: str):
    st.markdown("### 2. 现有模板")
    templates = list_templates(rt_key)
    active = get_active_template(rt_key)

    options = {f"{t.name}（{t.template_id} v{t.version}）": t.template_id for t in templates}
    active_label = next((k for k, v in options.items() if v == active.template_id), None)

    col1, col2 = st.columns([3, 1])
    with col1:
        chosen = st.selectbox(
            "选择模板", list(options.keys()), key=f"tpl_select_{rt_key}",
            index=list(options.keys()).index(active_label) if active_label else 0,
        )
    with col2:
        chosen_id = options[chosen]
        is_active = chosen_id == active.template_id
        st.write("")
        if st.button("✅ 已激活" if is_active else "设为激活", key=f"tpl_activate_{rt_key}",
                     use_container_width=True, disabled=is_active):
            set_active_template(rt_key, chosen_id)
            st.session_state[f"tpl_msg_{rt_key}"] = f"已激活模板：{chosen}"
            st.rerun()

    # 编辑按钮：把选中模板载入编辑器
    if st.button("✏️ 编辑选中模板", key=f"tpl_edit_load_{rt_key}"):
        tpl = next((t for t in templates if t.template_id == chosen_id), default_template(rt_key))
        st.session_state[f"tpl_edit_{rt_key}"] = tpl
        st.session_state[f"tpl_edit_src_{rt_key}"] = chosen_id


# ── 3. 编辑器 ───────────────────────────────────────────────────────────

def _render_editor(rt_key: str):
    tpl = st.session_state.get(f"tpl_edit_{rt_key}")
    if not tpl:
        return

    src_id = st.session_state.get(f"tpl_edit_src_{rt_key}", tpl.template_id)
    st.markdown(f"### 3. 编辑模板：{tpl.name}（{src_id}）")

    # 可编辑模块列表（用 session_state 持久化调序结果）
    mods_key = f"tpl_edit_mods_{rt_key}"
    if st.session_state.get(mods_key) is None:
        st.session_state[mods_key] = [m.__dict__.copy() for m in tpl.sorted_modules()]
    mods = st.session_state[mods_key]

    for i, m in enumerate(mods):
        with st.container():
            a, b, c, d = st.columns([3, 1, 1, 1])
            with a:
                m["title"] = st.text_input("标题", value=m["title"], key=f"tpl_mt_{rt_key}_{i}")
            with b:
                if st.button("↑", key=f"tpl_up_{rt_key}_{i}", disabled=(i == 0)):
                    mods[i], mods[i - 1] = mods[i - 1], mods[i]
            with c:
                if st.button("↓", key=f"tpl_dn_{rt_key}_{i}", disabled=(i == len(mods) - 1)):
                    mods[i], mods[i + 1] = mods[i + 1], mods[i]
            with d:
                if st.button("🗑", key=f"tpl_del_{rt_key}_{i}"):
                    mods.pop(i)
                    st.rerun()
            e1, e2, e3 = st.columns([1, 1, 2])
            with e1:
                m["llm_analysis"] = st.checkbox("LLM 分析", value=m.get("llm_analysis", False),
                                                key=f"tpl_la_{rt_key}_{i}")
            with e2:
                m["required"] = st.checkbox("必选", value=m.get("required", True),
                                            key=f"tpl_req_{rt_key}_{i}")
            with e3:
                # custom 暂不开放：RENDERER_REGISTRY 白名单未实现前，禁止 UI 把 render_kind
                # 设为 custom（防 report_editor 通过 UI 触达未处理的输入分支）。
                _render_kinds = ["line", "table", "list"]
                _cur = m.get("render_kind", "line")
                m["render_kind"] = st.selectbox(
                    "渲染方式", _render_kinds,
                    index=_render_kinds.index(_cur) if _cur in _render_kinds else 0,
                    key=f"tpl_rk_{rt_key}_{i}")
        st.markdown("---")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("➕ 添加模块", key=f"tpl_add_{rt_key}"):
            mods.append({"anchor": f"custom-{len(mods)+1}", "title": f"新模块 {len(mods)+1}",
                         "order": len(mods) + 1, "required": True, "data_binding": [],
                         "llm_analysis": False, "render_kind": "line", "chart": None,
                         "max_display": None, "feishu_verbosity": "data_only", "description": ""})
            st.rerun()
    with c2:
        if st.button("💾 保存修改", key=f"tpl_save_edit_{rt_key}", use_container_width=True):
            for i, m in enumerate(mods):
                m["order"] = i + 1
            new_tpl = ReportTemplate(
                template_id=tpl.template_id, template_type=tpl.template_type,
                version=tpl.version + 1, name=tpl.name,
                title_format=tpl.title_format, intro=tpl.intro,
                modules=[TemplateModule(**m) for m in mods],
                created_at=tpl.created_at,
            )
            save_template(new_tpl)
            st.session_state[f"tpl_msg_{rt_key}"] = f"已保存 {new_tpl.name} v{new_tpl.version}"
            st.session_state[mods_key] = None
            st.session_state[f"tpl_edit_{rt_key}"] = None
            st.rerun()
    with c3:
        if st.button("↩ 放弃", key=f"tpl_cancel_{rt_key}"):
            st.session_state[mods_key] = None
            st.session_state[f"tpl_edit_{rt_key}"] = None
            st.rerun()


def _render_module_table(modules):
    rows = "| 顺序 | 模块标题 | 锚点 | LLM分析 | 渲染 |\n|---|---|---|---|---|\n"
    for m in sorted(modules, key=lambda x: x.order if hasattr(x, "order") else 0):
        anchor = getattr(m, "anchor", "?")
        title = getattr(m, "title", "?")
        la = "✅" if getattr(m, "llm_analysis", False) else "—"
        rk = getattr(m, "render_kind", "line")
        order = getattr(m, "order", 0)
        rows += f"| {order} | {title} | {anchor} | {la} | {rk} |\n"
    st.markdown(rows)
