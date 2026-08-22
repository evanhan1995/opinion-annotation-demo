# -*- coding: utf-8 -*-
"""报告模板模型测试：默认模板结构 + 模板驱动 build_ir + 持久化 + 激活。"""
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from engine.report_model import (
    ReportTemplate, TemplateModule, default_template, save_template, load_template,
    list_templates, get_active_template, set_active_template,
)
from engine import report_model
from engine.report_ir import build_ir, render_md, render_html


@dataclass
class ReportData:
    date: str
    total_new_cases: int = 0
    avg_prev_7days: float = 0.0
    sentiment_dist: dict = field(default_factory=lambda: {"正面": 0, "中性": 0, "负面": 0})
    top_issues: list = field(default_factory=list)
    severity_dist: dict = field(default_factory=lambda: {"P0": 0, "P1": 0, "P2": 0, "P3": 0})
    platform_dist: dict = field(default_factory=dict)
    status_dist: dict = field(default_factory=dict)
    p0_p1_list: list = field(default_factory=list)
    monitor_stats: dict = field(default_factory=dict)


def _data():
    return ReportData(date="2026-08-19", total_new_cases=30, avg_prev_7days=17.6,
                      sentiment_dist={"正面": 13, "中性": 8, "负面": 9},
                      severity_dist={"P0": 1, "P1": 3, "P2": 0, "P3": 26},
                      platform_dist={"B站": 5, "抖音": 13, "微信": 12},
                      status_dist={"待跟进": 26, "处理中": 4})


# ── 默认模板结构 ────────────────────────────────────────────────────────

def test_default_daily_template_structure():
    tpl = default_template("daily")
    assert tpl.template_id == "default-daily"
    assert tpl.template_type == "daily"
    assert len(tpl.modules) == 6
    anchors = [m.anchor for m in tpl.sorted_modules()]
    assert anchors == ["volume-overview", "sentiment", "top-issues", "severity", "platform", "disposition"]
    # LLM 分析锚点与历史一致：volume/sentiment/disposition
    assert tpl.llm_anchors() == ["volume-overview", "sentiment", "disposition"]


def test_default_monthly_template_structure():
    tpl = default_template("monthly")
    assert len(tpl.modules) == 8
    assert tpl.sorted_modules()[6].anchor == "efficiency"
    assert tpl.sorted_modules()[7].anchor == "suggestions"
    # monthly severity 需要 LLM 分析
    assert "severity" in tpl.llm_anchors()


def test_template_driven_build_ir_equals_default():
    """模板驱动的 build_ir 与字符串形式（默认模板）产出等价结构。"""
    data = _data()
    ir_str = build_ir(data, "daily")
    ir_tpl = build_ir(data, default_template("daily"))
    assert [c.anchor for c in ir_str.chapters] == [c.anchor for c in ir_tpl.chapters]
    assert ir_tpl.metadata["template_id"] == "default-daily"
    assert ir_tpl.metadata["llm_anchors"] == ["volume-overview", "sentiment", "disposition"]


def test_custom_template_reorders_modules():
    """自定义模板可增删/调序模块。"""
    tpl = default_template("daily")
    # 删除 platform 模块，只保留其余
    tpl.modules = [m for m in tpl.modules if m.anchor != "platform"]
    ir = build_ir(_data(), tpl)
    assert [c.anchor for c in ir.chapters] == ["volume-overview", "sentiment", "top-issues", "severity", "disposition"]


def test_custom_render_kind_is_inert_and_safe():
    """安全边界：render_kind='custom' + 任意 render_template 不改变渲染、不被执行。

    锁定「render_template 仅是数据、绝不作为代码/渲染函数执行」这一不变式，
    防止未来有人实现 render_kind 驱动分发时引入可执行引用。"""
    tpl = default_template("daily")
    for m in tpl.modules:
        if m.anchor == "severity":
            m.render_kind = "custom"
            m.render_template = "__import__('os').system('echo PWNED_XYZ')"

    ir = build_ir(_data(), tpl)
    md = render_md(ir)
    html = render_html(ir)

    # render_template 内容不被执行、不被输出
    assert "PWNED_XYZ" not in md
    assert "PWNED_XYZ" not in html
    # severity 模块仍按 anchor 正常渲染（不抛异常、不静默丢失）
    assert "风险分级" in md
    assert "P0/P1" in html


def test_render_kind_does_not_drive_rendering():
    """render_kind 是模板层元数据，渲染只按 anchor 分发（忽略 render_kind）。"""
    tpl = default_template("daily")
    for m in tpl.modules:
        m.render_kind = "list"  # 全改成 list 不应改变任何渲染
    ir = build_ir(_data(), tpl)
    md = render_md(ir)
    # 仍含各模块标题（按 anchor 正常渲染）
    for t in ["声量概览", "情感分布", "风险分级", "平台分布", "处置状态统计"]:
        assert t in md


# ── 模板持久化 / 激活 ───────────────────────────────────────────────────

def test_template_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(report_model, "TEMPLATES_DIR", tmp_path)
    tpl = default_template("daily")
    tpl.template_id = "my-daily"
    tpl.version = 2
    save_template(tpl)
    loaded = load_template("daily", "my-daily")
    assert loaded.template_id == "my-daily"
    assert loaded.version == 2
    assert len(loaded.modules) == 6


def test_load_template_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.setattr(report_model, "TEMPLATES_DIR", tmp_path)
    tpl = load_template("daily", "nonexistent")
    assert tpl.template_id == "default-daily"


def test_active_template_set_and_get(tmp_path, monkeypatch):
    monkeypatch.setattr(report_model, "TEMPLATES_DIR", tmp_path)
    tpl = default_template("daily")
    tpl.template_id = "custom-daily"
    save_template(tpl)
    set_active_template("daily", "custom-daily")
    active = get_active_template("daily")
    assert active.template_id == "custom-daily"


def test_active_template_default_when_unset(tmp_path, monkeypatch):
    monkeypatch.setattr(report_model, "TEMPLATES_DIR", tmp_path)
    active = get_active_template("daily")
    assert active.template_id == "default-daily"
