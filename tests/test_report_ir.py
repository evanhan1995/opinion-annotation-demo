# -*- coding: utf-8 -*-
"""Tests for engine/report_ir.py — IR construction, validation, and dual rendering."""
from dataclasses import dataclass, field

import pytest
from engine.report_ir import (
    build_ir, validate_ir, render_md, render_html,
    ReportIR, Chapter,
)


# ── Mock ReportData (mirrors agents.daily_report.ReportData) ───────────

@dataclass
class ReportData:
    date: str
    total_new_cases: int = 0
    avg_prev_7days: float = 0.0
    sentiment_dist: dict = field(default_factory=lambda: {"正面": 0, "中性": 0, "负面": 0})
    top_issues: list[str] = field(default_factory=list)
    severity_dist: dict = field(default_factory=lambda: {"P0": 0, "P1": 0, "P2": 0, "P3": 0})
    platform_dist: dict = field(default_factory=dict)
    status_dist: dict = field(default_factory=dict)
    p0_p1_list: list[dict] = field(default_factory=list)
    monitor_stats: dict = field(default_factory=dict)


def _make_mock_data(**overrides) -> ReportData:
    defaults = dict(
        date="2026-06-01",
        total_new_cases=23,
        avg_prev_7days=18.5,
        sentiment_dist={"正面": 8, "中性": 10, "负面": 5},
        top_issues=["特斯拉召回事件", "AI监管新政策", "618电商大促", "高考舆情", "新能源补贴"],
        severity_dist={"P0": 0, "P1": 3, "P2": 12, "P3": 8},
        platform_dist={"微博": 8, "抖音": 6, "B站": 3, "小红书": 4, "微信": 2},
        status_dist={"待跟进": 5, "处理中": 3, "已处理": 10, "已放弃": 3, "忽略": 2},
        p0_p1_list=[
            {"severity": "P1", "title": "特斯拉召回引车主不满", "platform": "微博", "status": "处理中"},
            {"severity": "P1", "title": "AI生成虚假新闻引争议", "platform": "抖音", "status": "待跟进"},
        ],
    )
    defaults.update(overrides)
    return ReportData(**defaults)


# ── Tests: build_ir ────────────────────────────────────────────────────

def test_build_ir_daily():
    """build_ir daily: 6 chapters, data_rows values match input."""
    data = _make_mock_data()
    ir = build_ir(data, "daily")

    assert ir.report_type == "daily"
    assert ir.date == "2026-06-01"
    assert len(ir.chapters) == 6

    # Chapter 1: volume
    vol = ir.chapters[0]
    assert vol.anchor == "volume-overview"
    assert vol.data_rows["total_new_cases"] == 23
    assert vol.data_rows["avg_prev_7days"] == 18.5
    assert vol.data_rows["trend"] == "↑"
    assert vol.analysis == ""

    # Chapter 2: sentiment
    sent = ir.chapters[1]
    assert sent.anchor == "sentiment"
    assert sent.data_rows["positive_pct"] == 35
    assert sent.data_rows["neutral_pct"] == 43
    assert sent.data_rows["negative_pct"] == 22
    assert sent.chart is not None
    assert sent.chart["type"] == "pie"

    # Chapter 3: top-issues
    ti = ir.chapters[2]
    assert ti.anchor == "top-issues"
    assert len(ti.data_rows["items"]) == 5

    # Chapter 4: severity
    sev = ir.chapters[3]
    assert sev.anchor == "severity"
    assert sev.data_rows["p0_count"] == 0
    assert sev.data_rows["p1_count"] == 3
    assert sev.data_rows["p2_pct"] == 52
    assert len(sev.data_rows["p0p1_events"]) == 2
    assert sev.chart is not None

    # Chapter 5: platform
    plat = ir.chapters[4]
    assert plat.anchor == "platform"
    assert plat.data_rows["platforms"] == {"微博": 8, "抖音": 6, "B站": 3, "小红书": 4, "微信": 2}

    # Chapter 6: disposition
    disp = ir.chapters[5]
    assert disp.anchor == "disposition"
    assert disp.data_rows["pending"] == 5
    assert disp.data_rows["done"] == 10


def test_build_ir_monthly():
    """build_ir monthly: 8 chapters, includes efficiency and suggestions."""
    data = _make_mock_data(date="2026-05")
    ir = build_ir(data, "monthly")

    assert ir.report_type == "monthly"
    assert len(ir.chapters) == 8

    # Chapter 7: efficiency
    eff = ir.chapters[6]
    assert eff.anchor == "efficiency"
    assert eff.title == "七、处置效率统计"

    # Chapter 8: suggestions
    sug = ir.chapters[7]
    assert sug.anchor == "suggestions"
    assert sug.title == "八、下月监测建议"


def test_build_ir_empty_data():
    """build_ir with minimal/empty data still produces valid structure."""
    data = _make_mock_data(
        total_new_cases=0, avg_prev_7days=0,
        sentiment_dist={}, severity_dist={}, platform_dist={},
        status_dist={}, top_issues=[], p0_p1_list=[],
    )
    ir = build_ir(data, "daily")
    assert len(ir.chapters) == 6
    # trend should be → when avg is 0
    assert ir.chapters[0].data_rows["trend"] == "→"


# ── Tests: validate_ir ─────────────────────────────────────────────────

def _make_valid_ir() -> ReportIR:
    """Helper: build a valid IR with good analysis fields."""
    ir = ReportIR(report_type="daily", date="2026-06-01",
                  intro="今日舆情整体平稳，负面占比略有上升，P1事件集中在汽车和AI领域。")
    ir.chapters = [
        Chapter(anchor="volume-overview", title="测试1", data_rows={"x": 1},
                analysis="当日新增案例23条，较前7日均值上升24%，舆情热度明显增加，需关注后续走势。"),
        Chapter(anchor="sentiment", title="测试2", data_rows={"x": 1},
                analysis="整体情绪中性为主，负面占比22%略有上升，主要负面集中在特斯拉召回相关讨论。"),
        Chapter(anchor="top-issues", title="测试3", data_rows={"items": []}),
        Chapter(anchor="severity", title="测试4", data_rows={}),
        Chapter(anchor="platform", title="测试5", data_rows={}),
        Chapter(anchor="disposition", title="测试6", data_rows={},
                analysis="待跟进5条需重点关注，已处理10条完成率较高，整体处置响应速度符合预期。"),
    ]
    return ir


def test_validate_pass():
    """Valid IR passes validation."""
    ir = _make_valid_ir()
    ok, errors = validate_ir(ir)
    assert ok, f"Should pass: {errors}"


def test_validate_fail_empty_analysis():
    """Empty analysis triggers validation failure."""
    ir = _make_valid_ir()
    ir.chapters[0].analysis = ""  # volume-overview needs analysis
    ok, errors = validate_ir(ir)
    assert not ok
    assert any("为空" in e for e in errors)


def test_validate_fail_short_analysis():
    """Analysis shorter than 20 chars triggers failure."""
    ir = _make_valid_ir()
    ir.chapters[0].analysis = "太短"
    ok, errors = validate_ir(ir)
    assert not ok
    assert any("过短" in e for e in errors)


def test_validate_fail_placeholder():
    """Residual {{placeholder}} triggers failure."""
    ir = _make_valid_ir()
    ir.chapters[0].analysis = "这是{{占位符}}残留的分析文本，长度足够通过校验检查。"
    ok, errors = validate_ir(ir)
    assert not ok
    assert any("占位符" in e for e in errors)


def test_validate_empty_intro():
    """Empty or short intro triggers failure."""
    ir = _make_valid_ir()
    ir.intro = ""
    ok, errors = validate_ir(ir)
    assert not ok
    assert any("intro" in e for e in errors)


def test_validate_no_llm_chapters_always_pass():
    """Chapters without LLM analysis (top-issues, severity, platform) don't need validation."""
    ir = ReportIR(report_type="daily", date="2026-06-01", intro="足够长的导语至少十个字以上")
    ir.chapters = [
        # No LLM chapters — all are data-only
        Chapter(anchor="top-issues", title="测试", data_rows={"items": ["a", "b"]}),
        Chapter(anchor="severity", title="测试", data_rows={"p0_count": 0}),
        Chapter(anchor="platform", title="测试", data_rows={"platforms": {}}),
    ]
    ok, errors = validate_ir(ir)
    assert ok, f"Data-only chapters should pass: {errors}"


# ── Tests: render_md ───────────────────────────────────────────────────

def test_render_md_daily():
    """render_md daily: contains all 6 chapter titles and key numbers."""
    data = _make_mock_data()
    ir = build_ir(data, "daily")
    ir.intro = "今日舆情整体平稳。"
    for ch in ir.chapters:
        if ch.anchor in ("volume-overview", "sentiment", "disposition"):
            ch.analysis = "这是代码填充的模拟分析文本，足够长的测试内容超过二十个汉字。"

    md = render_md(ir)

    assert "# 舆情日报 2026-06-01" in md
    assert "一、声量概览" in md
    assert "二、情感分布" in md
    assert "三、关键议题 TOP5" in md
    assert "四、风险分级" in md
    assert "五、平台分布" in md
    assert "六、处置状态统计" in md
    assert "23" in md
    assert "18.5" in md
    assert "特斯拉召回事件" in md


def test_render_md_monthly():
    """render_md monthly: 8 chapters present."""
    data = _make_mock_data(date="2026-05")
    ir = build_ir(data, "monthly")
    ir.intro = "五月舆情整体平稳，负面占比有所上升。"
    for ch in ir.chapters:
        if ch.anchor in ("volume-overview", "sentiment", "severity", "disposition",
                         "efficiency", "suggestions"):
            ch.analysis = "分析文本足够长超过二十个汉字，提供有意义的舆情洞察和建议。"

    md = render_md(ir)

    assert "# 舆情月报 2026-05" in md
    assert "七、处置效率统计" in md
    assert "八、下月监测建议" in md
    assert "23" in md


# ── Tests: render_html ─────────────────────────────────────────────────

def test_render_html_contains_structure():
    """render_html produces valid HTML document with key elements."""
    data = _make_mock_data()
    ir = build_ir(data, "daily")
    ir.intro = "今日舆情整体平稳。"
    for ch in ir.chapters:
        if ch.anchor in ("volume-overview", "sentiment", "disposition"):
            ch.analysis = "模拟分析文本足够长的测试内容超过二十个汉字。"

    html = render_html(ir)

    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="zh-CN">' in html
    assert "<title>舆情监测日报 2026-06-01</title>" in html
    assert "</html>" in html
    assert "plotly" in html.lower()  # Plotly JS is embedded
    assert "舆情标注Wiki" in html


def test_render_html_contains_charts():
    """render_html includes Plotly chart divs."""
    data = _make_mock_data()
    ir = build_ir(data, "daily")
    ir.intro = "测试导语足够长。"
    for ch in ir.chapters:
        if ch.anchor in ("volume-overview", "sentiment", "disposition"):
            ch.analysis = "模拟分析文本足够长的测试内容超过二十个汉字。"

    html = render_html(ir)
    assert "chart-box" in html
    assert "Plotly" in html


# ── Test: MD/HTML sync ─────────────────────────────────────────────────

def test_md_html_sync():
    """Same IR renders key numbers consistently across MD and HTML."""
    data = _make_mock_data()
    ir = build_ir(data, "daily")
    ir.intro = "今日舆情整体平稳。"
    for ch in ir.chapters:
        if ch.anchor in ("volume-overview", "sentiment", "disposition"):
            ch.analysis = "模拟分析文本足够长超过二十汉字的测试内容。"

    md = render_md(ir)
    html = render_html(ir)

    # Key numbers appear in both
    for num in ["23", "18.5", "35", "43", "22"]:
        assert num in md, f"MD missing {num}"
        assert num in html, f"HTML missing {num}"

    # Chapter titles appear in MD (text report)
    for title in ["声量概览", "情感分布", "关键议题", "风险分级", "处置状态统计"]:
        assert title in md, f"MD missing {title}"
    # HTML is a dashboard — contains chart box headers instead
    for label in ["情感分布", "严重度分布", "P0/P1"]:
        assert label in html, f"HTML missing dashboard section: {label}"


# ── Test: edge cases ───────────────────────────────────────────────────

def test_trend_calculation():
    """_trend helper calculates direction correctly."""
    from engine.report_ir import _trend
    assert _trend(23, 18.5) == "↑"   # +24%
    assert _trend(15, 18.5) == "↓"   # -19%
    assert _trend(18, 18.5) == "→"   # within 10%
    assert _trend(5, 0) == "→"       # zero avg


def test_build_ir_trend_down():
    """Trend is ↓ when cases drop significantly."""
    data = _make_mock_data(total_new_cases=10, avg_prev_7days=18.5)
    ir = build_ir(data, "daily")
    assert ir.chapters[0].data_rows["trend"] == "↓"
