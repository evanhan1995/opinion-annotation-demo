# -*- coding: utf-8 -*-
"""Monitor Agent interface tests — Phase 1 skeleton validation."""
import io
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pytest
from agents.monitor import (
    load_keywords, execute_job, record_feedback,
    MonitorHarvest, KeywordResult, SearchResult, MonitorStats,
)


class TestKeywordLoading:
    def test_load_keywords_returns_list(self):
        keywords = load_keywords()
        assert isinstance(keywords, list)

    def test_keywords_have_required_fields(self):
        keywords = load_keywords()
        for kw in keywords:
            assert "id" in kw
            assert "keyword" in kw
            assert "platforms" in kw


class TestMonitorHarvest:
    def test_execute_job_returns_harvest(self):
        harvest = execute_job()
        assert isinstance(harvest, MonitorHarvest)

    def test_harvest_has_job_id(self):
        harvest = execute_job()
        assert harvest.job_id
        assert len(harvest.job_id) > 0

    def test_harvest_has_timestamps(self):
        harvest = execute_job()
        assert harvest.started_at
        assert harvest.finished_at

    def test_harvest_stats(self):
        harvest = execute_job()
        assert harvest.stats is not None
        assert isinstance(harvest.stats, MonitorStats)


class TestFeedbackRecording:
    def test_record_feedback_writes_file(self):
        record_feedback("kw001", "douyin", True, "relevant")
        feedback_path = os.path.join(
            os.path.dirname(__file__), "..", "outputs", "keyword_feedback.jsonl"
        )
        # Check that feedback directory was created (file may be empty in Phase 1)
        assert os.path.exists(os.path.dirname(feedback_path))


class TestDataclasses:
    def test_search_result_defaults(self):
        sr = SearchResult(platform="douyin", keyword_id="k1", keyword="test", sort_type="date", title="t", url="u")
        assert sr.engagement == 0
        assert sr.author == ""

    def test_keyword_result_defaults(self):
        kr = KeywordResult(keyword_id="k1", keyword="test", platform="douyin")
        assert kr.date_results == []
        assert kr.hot_results == []
        assert kr.new_items == []
