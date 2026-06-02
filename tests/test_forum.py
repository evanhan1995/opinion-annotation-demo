# -*- coding: utf-8 -*-
"""Tests for Forum Agent — cross-platform annotation cross-validation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.forum import (
    _detect_contradictions_heuristic,
    _read_case_annotation,
    cross_validate,
)
from agents.shared import ForumResult


class TestHeuristicDetection:
    """Verify contradiction detection heuristics."""

    def test_severity_gap_detected(self):
        """Severity gap >= 2 should be flagged."""
        current = {"case_id": "case-001", "platform": "weibo", "severity": "P0", "sentiment": "负面"}
        related = [
            {"case_id": "case-002", "platform": "xiaohongshu", "severity": "P2", "sentiment": "中性"}
        ]
        issues = _detect_contradictions_heuristic(current, related)
        assert len(issues) >= 1
        assert "Severity gap" in issues[0]

    def test_sentiment_conflict_detected(self):
        """Opposite sentiment should be flagged."""
        current = {"case_id": "case-001", "platform": "weibo", "severity": "P2", "sentiment": "负面"}
        related = [
            {"case_id": "case-002", "platform": "xiaohongshu", "severity": "P2", "sentiment": "正面"}
        ]
        issues = _detect_contradictions_heuristic(current, related)
        assert len(issues) >= 1
        assert "Sentiment conflict" in issues[0]

    def test_small_severity_gap_not_flagged(self):
        """Severity gap of 1 should not be flagged."""
        current = {"case_id": "case-001", "platform": "weibo", "severity": "P2", "sentiment": "中性"}
        related = [
            {"case_id": "case-002", "platform": "xiaohongshu", "severity": "P3", "sentiment": "中性"}
        ]
        issues = _detect_contradictions_heuristic(current, related)
        assert len(issues) == 0

    def test_same_sentiment_not_flagged(self):
        """Same sentiment across platforms should not flag."""
        current = {"case_id": "case-001", "platform": "weibo", "severity": "P2", "sentiment": "负面"}
        related = [
            {"case_id": "case-002", "platform": "xiaohongshu", "severity": "P3", "sentiment": "负面"}
        ]
        issues = _detect_contradictions_heuristic(current, related)
        assert len(issues) == 0

    def test_empty_related(self):
        """No related cases should yield no contradictions."""
        issues = _detect_contradictions_heuristic({"case_id": "x", "severity": "P1"}, [])
        assert len(issues) == 0

    def test_multiple_contradictions(self):
        """Multiple related cases can yield multiple issues."""
        current = {"case_id": "case-001", "platform": "weibo", "severity": "P0", "sentiment": "负面"}
        related = [
            {"case_id": "case-002", "platform": "xiaohongshu", "severity": "P2", "sentiment": "中性"},
            {"case_id": "case-003", "platform": "douyin", "severity": "P3", "sentiment": "正面"},
        ]
        issues = _detect_contradictions_heuristic(current, related)
        assert len(issues) >= 2


class TestForumResult:
    """Verify ForumResult dataclass."""

    def test_forum_result_defaults(self):
        fr = ForumResult(case_id="test")
        assert fr.case_id == "test"
        assert fr.related_cases == []
        assert fr.contradictions == []
        assert fr.needs_review is False

    def test_forum_result_with_contradictions(self):
        fr = ForumResult(
            case_id="test",
            related_cases=["case-001"],
            contradictions=["Severity gap: P0 vs P2"],
            host_verdict="建议复核",
            needs_review=True,
        )
        assert fr.needs_review is True
        assert len(fr.contradictions) == 1


class TestCrossValidateNoCases:
    """Test cross_validate when no wiki cases exist (graceful degradation)."""

    def test_cross_validate_no_cases(self):
        """cross_validate should handle missing cases gracefully."""
        # When no cases exist in wiki/cases/, should return empty result
        result = cross_validate("nonexistent-case-999.md", {
            "severity": "P2", "sentiment": "中性", "platform": "weibo"
        })
        assert isinstance(result, ForumResult)
        assert result.needs_review is False
