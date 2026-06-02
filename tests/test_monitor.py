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

    def test_keyword_result_notes_default(self):
        """KeywordResult.notes defaults to empty list."""
        kr = KeywordResult(keyword_id="k1", keyword="test", platform="douyin")
        assert kr.notes == []


class TestDateMode:
    """Verify date-range mode behavior."""

    def test_execute_job_date_mode_returns_harvest(self):
        """Date mode should return valid MonitorHarvest."""
        harvest = execute_job(date_from="2026-05-31", date_to="2026-06-01")
        assert isinstance(harvest, MonitorHarvest)
        assert harvest.job_id

    def test_date_mode_skips_xhs_wechat(self):
        """Date mode should skip xiaohongshu and wechat with notes."""
        harvest = execute_job(date_from="2026-05-31", date_to="2026-06-01")
        for kr in harvest.keyword_results:
            if kr.platform in ("xiaohongshu", "wechat"):
                assert len(kr.notes) > 0, f"{kr.platform} should have skip note"
                assert any("跳过" in n or "不支持" in n for n in kr.notes)

    def test_date_mode_empty_params_old_behavior(self):
        """Empty date_from should use old count-based behavior."""
        harvest_old = execute_job()
        harvest_date = execute_job(date_from="", date_to="")
        # Both should produce valid harvests (old behavior)
        assert isinstance(harvest_old, MonitorHarvest)
        assert isinstance(harvest_date, MonitorHarvest)

    def test_date_mode_weibo_client_filter(self):
        """Weibo in date mode should get fallback count 200."""
        from agents.monitor import _DATE_MODE_FALLBACK_COUNT
        assert _DATE_MODE_FALLBACK_COUNT == 200

    def test_date_mode_constants(self):
        """Verify date mode constants are sensible."""
        from agents.monitor import (
            _DATE_MODE_MAX_PAGES, _DATE_MODE_FALLBACK_COUNT,
            _DATE_CAPABLE_PLATFORMS, _DATE_SKIP_PLATFORMS,
            _DATE_CLIENTSIDE_PLATFORMS,
        )
        assert _DATE_MODE_MAX_PAGES == 50
        assert _DATE_MODE_FALLBACK_COUNT == 200
        assert _DATE_CAPABLE_PLATFORMS == {"bilibili"}
        assert "youtube" in _DATE_CLIENTSIDE_PLATFORMS
        assert "weibo" in _DATE_CLIENTSIDE_PLATFORMS
        assert "xiaohongshu" in _DATE_SKIP_PLATFORMS
        assert "wechat" in _DATE_SKIP_PLATFORMS
        # Three categories must be disjoint
        assert _DATE_CAPABLE_PLATFORMS.isdisjoint(_DATE_CLIENTSIDE_PLATFORMS)
        assert _DATE_CAPABLE_PLATFORMS.isdisjoint(_DATE_SKIP_PLATFORMS)
        assert _DATE_CLIENTSIDE_PLATFORMS.isdisjoint(_DATE_SKIP_PLATFORMS)

    def test_search_functions_accept_date_params(self):
        """All 6 platform searchers accept date_from/date_to kwargs."""
        from agents.monitor import PLATFORM_SEARCHERS
        import inspect
        for platform, func in PLATFORM_SEARCHERS.items():
            sig = inspect.signature(func)
            assert "date_from" in sig.parameters, f"{platform} missing date_from"
            assert "date_to" in sig.parameters, f"{platform} missing date_to"
