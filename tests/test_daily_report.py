# -*- coding: utf-8 -*-
"""Daily Report Agent interface tests — Phase 1 skeleton validation."""
import io
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pytest
from pathlib import Path
from agents.daily_report import (
    generate_daily, generate_monthly, ReportData,
    _pct, _list_as_md, _p0p1_as_md, _platform_as_md,
)


class TestDailyReport:
    def test_generate_returns_path(self):
        path = generate_daily("2026-05-23")
        assert "2026-05-23" in path

    def test_generate_creates_file(self):
        path = generate_daily("2026-05-23")
        assert os.path.exists(path)

    def test_output_is_markdown(self):
        path = generate_daily("2026-05-23")
        content = Path(path).read_text(encoding="utf-8")
        assert content.startswith("# 舆情日报")
        assert "声量概览" in content
        assert "情感分布" in content
        assert "风险分级" in content
        assert "处置状态统计" in content


class TestMonthlyReport:
    def test_generate_returns_path(self):
        path = generate_monthly("2026-05")
        assert "2026-05" in path

    def test_generate_creates_file(self):
        path = generate_monthly("2026-05")
        assert os.path.exists(path)

    def test_output_is_markdown(self):
        path = generate_monthly("2026-05")
        content = Path(path).read_text(encoding="utf-8")
        assert content.startswith("# 舆情月报")
        assert "声量趋势" in content
        assert "处置效率统计" in content


class TestHelpers:
    def test_pct_zero_total(self):
        assert _pct({}, "x") == 0

    def test_pct_calculation(self):
        assert _pct({"正面": 3, "中性": 2, "负面": 5}, "负面") == 50

    def test_list_as_md(self):
        result = _list_as_md(["A", "B"])
        assert "1. A" in result
        assert "2. B" in result

    def test_list_as_md_empty(self):
        result = _list_as_md([])
        assert "暂无数据" in result

    def test_platform_as_md_empty(self):
        assert "暂无数据" in _platform_as_md({})
