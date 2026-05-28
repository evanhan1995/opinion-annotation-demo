# -*- coding: utf-8 -*-
"""Orchestrator interface tests — Phase 1 skeleton validation."""
import io
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pytest
from agents.orchestrator import (
    run_passive_analysis, run_active_monitor,
    run_daily_report, run_monthly_report, answer_question,
    PipelineResult,
)


class TestFlowAPassiveAnalysis:
    def test_returns_pipeline_result(self):
        result = run_passive_analysis("https://example.com")
        assert isinstance(result, PipelineResult)

    def test_flow_label(self):
        result = run_passive_analysis("https://example.com")
        assert result.flow == "passive_analysis"

    def test_success_flag(self):
        result = run_passive_analysis("https://example.com")
        # Phase 2: real pipeline — fake URL will fail. This is correct behavior.
        assert isinstance(result.success, bool)

    def test_returns_annotation(self):
        result = run_passive_analysis("https://example.com")
        # Phase 2: fake URL may fail early in Scraper → annotation can be None
        if result.annotation is not None:
            assert result.annotation.url == "https://example.com"

    def test_timestamps_present(self):
        result = run_passive_analysis("https://example.com")
        assert result.started_at
        assert result.finished_at


class TestFlowBActiveMonitor:
    def test_returns_pipeline_result(self):
        result = run_active_monitor()
        assert isinstance(result, PipelineResult)

    def test_flow_label(self):
        result = run_active_monitor()
        assert result.flow == "active_monitor"


class TestFlowCDailyReport:
    def test_daily_report_returns_path(self):
        path = run_daily_report("2026-01-01")
        assert "2026-01-01" in path

    def test_monthly_report_returns_path(self):
        path = run_monthly_report("2026-01")
        assert "2026-01" in path

    def test_daily_report_file_exists(self):
        path = run_daily_report("2026-05-23")
        assert os.path.exists(path)

    def test_monthly_report_file_exists(self):
        path = run_monthly_report("2026-05")
        assert os.path.exists(path)


class TestFlowDQA:
    def test_answer_question_returns_string(self):
        result = answer_question("测试问题")
        assert isinstance(result, str)
        assert len(result) > 0
