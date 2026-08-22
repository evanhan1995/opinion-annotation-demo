# -*- coding: utf-8 -*-
"""飞书渲染器测试：模块/数据/P0P1 全量一致，绝不静默丢弃。"""
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from engine.report_model import FinalReport
from shared import report_renderers as rr


def _make_fr(p0p1_events=None):
    events = p0p1_events if p0p1_events is not None else [
        {"severity": "P0", "title": "事件0", "platform": "抖音"},
        {"severity": "P1", "title": "事件1", "platform": "微信"},
        {"severity": "P1", "title": "事件2", "platform": "微信"},
        {"severity": "P1", "title": "事件3", "platform": "微信"},
    ]
    return FinalReport(
        report_id="daily-2026-08-19", report_type="daily", report_date="2026-08-19",
        template_id="default-daily", template_version=1, generated_at="2026-08-19T21:07:00",
        markdown="# 舆情日报 2026-08-19",
        ir={"report_type": "daily", "date": "2026-08-19", "chapters": [
            {"anchor": "volume-overview", "title": "一、声量概览",
             "data_rows": {"total_new_cases": 30, "avg_prev_7days": 17.6, "trend": "↑"},
             "analysis": "声量上升"},
            {"anchor": "sentiment", "title": "二、情感分布",
             "data_rows": {"positive_pct": 43, "neutral_pct": 27, "negative_pct": 30},
             "analysis": "负面偏高"},
            {"anchor": "severity", "title": "四、风险分级",
             "data_rows": {"p0_count": 1, "p1_count": 3, "p2_count": 0, "p3_count": 26,
                           "p0p1_events": events}, "analysis": ""},
            {"anchor": "platform", "title": "五、平台分布",
             "data_rows": {"platforms": {"B站": 5, "抖音": 13, "微信": 12}}, "analysis": ""},
            {"anchor": "disposition", "title": "六、处置状态统计",
             "data_rows": {"pending": 26, "in_progress": 4, "done": 0, "abandoned": 0, "ignored": 0},
             "analysis": "积压突出"},
        ]},
    )


def test_render_feishu_all_p0p1_present():
    """4 条 P0/P1 必须全部出现（2026-08-19 案例138 场景不丢失）。"""
    fr = _make_fr()
    title, body, fields = rr.render_feishu(fr)
    assert body.count("[P0]") == 1
    assert body.count("[P1]") == 3


def test_render_feishu_no_title_truncation():
    """标题不截断（去掉旧的 [:40]）。"""
    long_title = "这是一个非常非常长的标题" * 10
    fr = _make_fr(p0p1_events=[{"severity": "P1", "title": long_title, "platform": "抖音"}])
    _, body, _ = rr.render_feishu(fr)
    assert long_title in body


def test_render_feishu_module_order_preserved():
    """模块顺序与 FinalReport 一致。"""
    fr = _make_fr()
    _, body, _ = rr.render_feishu(fr)
    idx = [body.index(t) for t in ["声量概览", "情感分布", "风险分级", "平台分布", "处置状态统计"]]
    assert idx == sorted(idx)


def test_render_feishu_verbosity_data_only_omits_analysis():
    """data_only 模块不含分析段；full 模块含分析段。"""
    fr = _make_fr()
    _, body, _ = rr.render_feishu(fr)
    assert "负面偏高" not in body          # sentiment = data_only
    assert "声量上升" in body              # volume-overview = full
    assert "积压突出" in body              # disposition = full


def test_render_feishu_verbosity_override():
    """verbosity 参数可覆盖默认配置。"""
    fr = _make_fr()
    _, body, _ = rr.render_feishu(fr, verbosity={"sentiment": "full"})
    assert "负面偏高" in body


def test_render_web_returns_markdown():
    fr = _make_fr()
    assert rr.render_web(fr) == "# 舆情日报 2026-08-19"


def test_format_p0p1_max_display_marks_hidden():
    """max_display 超限时明确提示「另有 N 条未展开」，不静默丢弃。"""
    events = [{"severity": "P1", "title": f"事件{i}", "platform": "微信"} for i in range(10)]
    out = rr._format_p0p1(events, max_events=3)
    assert out.count("[P1]") == 3
    assert "另有 7 条未展开" in out


def test_degrade_oversize_preserves_p0_and_marks_p1(monkeypatch):
    """超长时二级降级：P0 全量 + P1 前 N + 提示 + 报告链接，不静默截断。

    构造 1 条 P0 + 50 条 P1（远超阈值），断言降级格式：
    P0 全量保留，P1 只保留 FEISHU_MAX_P0P1 条并明确标注「另有 30 条 P1 未展开」。
    """
    monkeypatch.setattr(rr, "FEISHU_MAX_CHARS", 60)
    many_p1 = [{"severity": "P0", "title": "P0事件", "platform": "抖音"}] + \
              [{"severity": "P1", "title": f"P1事件{i}", "platform": "微信"} for i in range(50)]
    fr = _make_fr(p0p1_events=many_p1)
    _, body, _ = rr.render_feishu(fr)

    # 降级头 + P0 全量段
    assert "P0 事件：" in body
    assert body.count("[P0]") == 1
    assert "P0事件" in body
    # P1 部分段：只保留 FEISHU_MAX_P0P1 条
    assert "P1 事件（部分）：" in body
    assert body.count("[P1]") == rr.FEISHU_MAX_P0P1
    # 明确提示剩余数量 + 报告链接
    assert "另有 30 条 P1 未展开" in body
    assert "完整报告见" in body
