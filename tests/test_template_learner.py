# -*- coding: utf-8 -*-
"""Markdown 案例学习器测试：解析、脱敏、抽样、兜底。"""
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from engine import report_template_learner as learner
from engine.report_model import ReportTemplate


DAILY_EXAMPLE = """# 舆情日报 2026-08-19

## 一、声量概览
当日新增案例 30 条，较前7日均值 17.6 条。

## 二、情感分布
正面 43% | 中性 27% | 负面 30%

## 三、关键议题 TOP5
1. 议题A
2. 议题B

## 四、风险分级
| 级别 | 数量 | 占比 |
|------|------|------|
| P0 | 1 | 3% |

## 五、平台分布
- 抖音：13 条

## 六、处置状态统计
- 待跟进：26
"""


def test_redact_numbers():
    assert learner.redact_numbers("30 条，均值 17.6 条，占比 43%") == "{n} 条，均值 {n} 条，占比 {n}"


def test_parse_sections_extracts_titles_in_order():
    sections = learner.parse_sections(DAILY_EXAMPLE)
    titles = [s["title"] for s in sections]
    assert titles[:3] == ["一、声量概览", "二、情感分布", "三、关键议题 TOP5"]
    assert "六、处置状态统计" in titles


def test_parse_sections_redacts_numbers():
    sections = learner.parse_sections(DAILY_EXAMPLE)
    vol = next(s for s in sections if s["title"] == "一、声量概览")
    assert "30" not in vol["snippet"]
    assert "{n}" in vol["snippet"]


def test_parse_sections_detects_table_and_list():
    sections = learner.parse_sections(DAILY_EXAMPLE)
    sev = next(s for s in sections if s["title"] == "四、风险分级")
    assert sev["has_table"] is True
    plat = next(s for s in sections if s["title"] == "五、平台分布")
    assert plat["has_list"] is True


def test_structure_signature_and_select_representative_dedup():
    p1 = learner.parse_sections(DAILY_EXAMPLE)
    p2 = learner.parse_sections(DAILY_EXAMPLE)  # 相同结构
    chosen = learner.select_representative([p1, p2], limit=10)
    assert len(chosen) == 1


def test_select_representative_samples_when_over_limit():
    # 构造 25 个不同结构的案例，上限 10 → 抽样到 10
    many = []
    for i in range(25):
        many.append([{"title": f"模块{i}", "snippet": "", "has_table": False, "has_list": False}])
    chosen = learner.select_representative(many, limit=10)
    assert len(chosen) == 10


def test_map_anchor_known_keywords():
    assert learner._map_anchor("一、声量概览") == "volume-overview"
    assert learner._map_anchor("二、情感分布") == "sentiment"
    assert learner._map_anchor("六、处置状态统计") == "disposition"


def test_fallback_template_produces_report_template():
    parsed = [learner.parse_sections(DAILY_EXAMPLE)]
    tpl = learner._fallback_template(parsed, "daily")
    assert isinstance(tpl, ReportTemplate)
    assert tpl.template_type == "daily"
    assert len(tpl.modules) >= 5
    # 声量模块映射到 volume-overview
    anchors = [m.anchor for m in tpl.modules]
    assert "volume-overview" in anchors
    assert "sentiment" in anchors


def test_learn_template_falls_back_without_llm(monkeypatch):
    """LLM 不可用时回退确定性兜底，不抛异常。"""

    def boom(*a, **k):
        raise RuntimeError("no llm")

    monkeypatch.setattr(learner, "get_llm", boom)
    tpl = learner.learn_template_from_examples([DAILY_EXAMPLE], "daily")
    assert isinstance(tpl, ReportTemplate)
    assert tpl.template_type == "daily"


def test_learn_template_empty_input_returns_default():
    tpl = learner.learn_template_from_examples([], "daily")
    assert tpl.template_id == "default-daily"
