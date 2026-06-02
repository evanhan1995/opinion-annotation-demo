# -*- coding: utf-8 -*-
"""Tests for ReportEngine chart generation (P5)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.daily_report import (
    ReportData,
    generate_daily_html,
    generate_monthly_html,
)
from engine.report_ir import (
    _read_plotly_min_js,
    _plot_sentiment_pie,
    _plot_severity_bar,
    _plot_platform_bar,
    build_ir,
)


@pytest.fixture
def sample_data():
    """Create a sample ReportData for chart testing."""
    return ReportData(
        date="2026-05-31",
        total_new_cases=15,
        avg_prev_7days=12.5,
        sentiment_dist={"正面": 5, "中性": 7, "负面": 3},
        severity_dist={"P0": 0, "P1": 2, "P2": 5, "P3": 8},
        platform_dist={"微博": 5, "小红书": 4, "抖音": 3, "B站": 2, "知乎": 1},
        top_issues=["产品质量", "客服投诉", "物流问题"],
        status_dist={"待跟进": 8, "处理中": 4, "已处理": 2, "已放弃": 1, "忽略": 0},
    )


@pytest.fixture
def empty_data():
    """Empty data for edge case testing."""
    return ReportData(date="2026-05-31")


class TestPlotlyCharts:
    """Verify Plotly chart generation functions."""

    def test_sentiment_pie_returns_html(self, sample_data):
        ir = build_ir(sample_data, "daily")
        chart = _plot_sentiment_pie(ir)
        assert "plotly" in chart.lower() or "Plotly" in chart or "<div" in chart
        assert len(chart) > 0

    def test_severity_bar_returns_html(self, sample_data):
        ir = build_ir(sample_data, "daily")
        chart = _plot_severity_bar(ir)
        assert len(chart) > 0

    def test_platform_bar_returns_html(self, sample_data):
        ir = build_ir(sample_data, "daily")
        chart = _plot_platform_bar(ir)
        assert len(chart) > 0

    def test_sentiment_pie_empty_data(self, empty_data):
        """Empty data should not crash."""
        ir = build_ir(empty_data, "daily")
        chart = _plot_sentiment_pie(ir)
        assert chart == ""

    def test_platform_bar_empty_data(self, empty_data):
        ir = build_ir(empty_data, "daily")
        chart = _plot_platform_bar(ir)
        assert chart == ""


class TestHTMLReport:
    """Verify HTML report generation."""

    def test_generate_daily_html_creates_file(self, sample_data, tmp_path):
        """Should create an HTML file."""
        # Override REPORTS_DAILY_DIR temporarily
        import agents.daily_report as dr
        original_dir = dr.REPORTS_DAILY_DIR
        dr.REPORTS_DAILY_DIR = tmp_path

        try:
            path = generate_daily_html(sample_data)
            assert Path(path).exists()
            html = Path(path).read_text(encoding="utf-8")
            assert "<html" in html.lower()
            assert "plotly" in html.lower()
        finally:
            dr.REPORTS_DAILY_DIR = original_dir

    def test_html_report_contains_data(self, sample_data, tmp_path):
        """HTML should contain the data values."""
        import agents.daily_report as dr
        original_dir = dr.REPORTS_DAILY_DIR
        dr.REPORTS_DAILY_DIR = tmp_path

        try:
            path = generate_daily_html(sample_data)
            html = Path(path).read_text(encoding="utf-8")
            assert "15" in html  # total cases
        finally:
            dr.REPORTS_DAILY_DIR = original_dir


    def test_html_offline_no_cdn(self, sample_data, tmp_path):
        """Generated HTML should NOT reference external CDN."""
        import agents.daily_report as dr
        original_dir = dr.REPORTS_DAILY_DIR
        dr.REPORTS_DAILY_DIR = tmp_path
        try:
            path = generate_daily_html(sample_data)
            html = Path(path).read_text(encoding="utf-8")
            assert '<script src="https://cdn.plot.ly' not in html
            assert '<script src="http' not in html or 'plotly' not in html.lower()
        finally:
            dr.REPORTS_DAILY_DIR = original_dir

    def test_html_has_cover_page(self, sample_data, tmp_path):
        """HTML should contain cover page with title and metric cards."""
        import agents.daily_report as dr
        original_dir = dr.REPORTS_DAILY_DIR
        dr.REPORTS_DAILY_DIR = tmp_path
        try:
            path = generate_daily_html(sample_data)
            html = Path(path).read_text(encoding="utf-8")
            assert 'class="cover"' in html
            assert "舆情监测日报" in html
            assert 'class="metrics"' in html
            assert 'class="card' in html
            assert "P0/P1" in html
        finally:
            dr.REPORTS_DAILY_DIR = original_dir

    def test_html_has_print_styles(self, sample_data, tmp_path):
        """HTML should include @media print CSS."""
        import agents.daily_report as dr
        original_dir = dr.REPORTS_DAILY_DIR
        dr.REPORTS_DAILY_DIR = tmp_path
        try:
            path = generate_daily_html(sample_data)
            html = Path(path).read_text(encoding="utf-8")
            assert "@media print" in html
        finally:
            dr.REPORTS_DAILY_DIR = original_dir

    def test_monthly_html_creates_file(self, sample_data, tmp_path):
        """generate_monthly_html should create a .html file."""
        import agents.daily_report as dr
        original_dir = dr.REPORTS_MONTHLY_DIR
        dr.REPORTS_MONTHLY_DIR = tmp_path
        try:
            path = generate_monthly_html(sample_data)
            assert Path(path).exists()
            html = Path(path).read_text(encoding="utf-8")
            assert "舆情监测月报" in html
        finally:
            dr.REPORTS_MONTHLY_DIR = original_dir


class TestPlotlyJSReader:
    """Verify Plotly.js embedding helper."""

    def test_read_plotly_min_js_returns_string(self):
        js = _read_plotly_min_js()
        assert isinstance(js, str)
        assert len(js) > 100000  # at least 100KB

    def test_read_plotly_min_js_is_cached(self):
        a = _read_plotly_min_js()
        b = _read_plotly_min_js()
        assert a is b  # same object, cached


class TestReportData:
    """Verify ReportData dataclass defaults."""

    def test_report_data_defaults(self):
        rd = ReportData(date="test")
        assert rd.date == "test"
        assert rd.total_new_cases == 0
        assert rd.sentiment_dist == {"正面": 0, "中性": 0, "负面": 0}
