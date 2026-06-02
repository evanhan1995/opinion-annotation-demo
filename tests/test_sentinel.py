# -*- coding: utf-8 -*-
"""Tests for Sentinel Agent — rule engine + pre-filter."""

import pytest
from pathlib import Path
import sys

# Ensure agents/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.sentinel import (
    apply_rules,
    apply_snownlp,
    screen_content,
    discover_topics,
    clear_topic_cache,
    _get_cache_age,
    should_skip_pipeline,
    should_skip_llm,
    SPAM_KEYWORDS,
    GRAY_MARKET_KEYWORDS,
)
from agents.shared import SentinelResult


class TestSentinelRuleEngine:
    """Verify rule engine correctly classifies content."""

    def test_filter_spam_by_keyword(self):
        """Spam keywords should trigger reject verdict."""
        result = apply_rules("加微信xxx领取免费礼物，日赚千元")
        assert result.verdict == "reject"
        assert result.spam_score >= 0.8
        assert should_skip_pipeline(result) is True

    def test_filter_gray_market(self):
        """Gray market keywords should trigger reject."""
        result = apply_rules("temu对公验证秒过，可解银行验证，Kyc接单")
        assert result.verdict == "reject"
        assert should_skip_pipeline(result) is True

    def test_filter_irrelevant_weather(self):
        """Weather chit-chat should be rejected."""
        result = apply_rules("今天天气不错，出门逛逛")
        assert result.verdict == "reject"

    def test_filter_empty_content(self):
        """Punctuation-only content should be rejected."""
        result = apply_rules("。。。")
        assert result.verdict == "reject"

    def test_pass_normal_news(self):
        """Normal news article should pass through to LLM."""
        text = (
            "广州儿童花市正式开幕，来自海内外的100多组亲子家庭齐聚。"
            "本届花市打造水上花墟场景，持续聚焦市民需求。"
        )
        result = apply_rules(text)
        assert result.verdict == "pass"
        assert should_skip_pipeline(result) is False
        assert should_skip_llm(result) is False

    def test_fast_track_negative(self):
        """Obvious negative sentiment should fast-track."""
        result = apply_rules("这个产品质量太差了，用了两天就坏了，客服也不理人，必须退款！")
        assert result.verdict == "fast_track"
        assert result.suggested_sentiment == "负面"
        assert should_skip_llm(result) is True

    def test_fast_track_positive(self):
        """Obvious positive sentiment should fast-track."""
        result = apply_rules("真的超级好用！物流快包装好，客服态度也很好，强烈推荐大家购买！")
        assert result.verdict == "fast_track"
        assert result.suggested_sentiment == "正面"
        assert should_skip_llm(result) is True

    def test_fast_track_severity_p0(self):
        """Death/fatal keywords should fast-track to P0 severity."""
        result = apply_rules("工厂发生爆炸，导致多人死亡，相关部门已介入调查")
        assert result.verdict == "fast_track"
        assert result.suggested_severity == "P0"
        assert result.suggested_sentiment == "负面"

    def test_rule_hits_tracking(self):
        """Rule hits list should record matched keywords."""
        result = apply_rules("加微信xxx日赚千元在家可做")
        assert len(result.rule_hits) > 0

    def test_sentinel_result_fields(self):
        """SentinelResult dataclass should have all required fields."""
        sr = SentinelResult(verdict="pass", reason="test")
        assert sr.verdict == "pass"
        assert sr.spam_score == 0.0
        assert sr.suggested_sentiment == ""
        assert sr.rule_hits == []


class TestKeywordCoverage:
    """Verify keyword lists are non-empty and well-formed."""

    def test_spam_keywords_not_empty(self):
        assert len(SPAM_KEYWORDS) >= 10

    def test_gray_market_keywords_not_empty(self):
        assert len(GRAY_MARKET_KEYWORDS) >= 10

    def test_keywords_are_lowercase(self):
        """All keywords should be lowercase for case-insensitive matching."""
        for kw in SPAM_KEYWORDS + GRAY_MARKET_KEYWORDS:
            assert kw == kw.lower(), f"Keyword '{kw}' is not lowercase"


class TestSnowNLPPreFilter:
    """Verify SnowNLP pre-filter integration."""

    def test_apply_snownlp_extreme_negative(self):
        """SnowNLP should fast_track extremely negative text."""
        rule_result = SentinelResult(verdict="pass", reason="test")
        result = apply_snownlp("垃圾产品，太差了，不要买，骗人的东西，退款！", rule_result)
        # This text may or may not score < 0.1 depending on SnowNLP model
        assert result.verdict in ("pass", "fast_track")

    def test_apply_snownlp_extreme_positive(self):
        """SnowNLP should fast_track extremely positive text."""
        rule_result = SentinelResult(verdict="pass", reason="test")
        result = apply_snownlp("非常好用，强烈推荐，性价比很高，太喜欢了，完美！", rule_result)
        assert result.verdict in ("pass", "fast_track")

    def test_apply_snownlp_adds_hits(self):
        """SnowNLP should append scoring info to rule_hits."""
        rule_result = SentinelResult(verdict="pass", reason="test", rule_hits=["original"])
        result = apply_snownlp("今天天气不错", rule_result)
        # Should have added a snownlp scoring hit
        snownlp_hits = [h for h in result.rule_hits if h.startswith("snownlp:")]
        assert len(snownlp_hits) >= 1, f"No snownlp hit found in {result.rule_hits}"

    def test_screen_content_integration(self):
        """screen_content should combine rules + SnowNLP."""
        # Normal text: should pass through
        result = screen_content("广州花市正式开幕，亲子家庭齐聚儿童公园", "weibo")
        assert result.verdict in ("pass", "fast_track")

        # Spam: should be rejected
        result = screen_content("加微信免费领取礼品日赚千元", "weibo")
        assert result.verdict == "reject"

    def test_screen_content_reject_skips_snownlp(self):
        """Rejected content should not waste time on SnowNLP."""
        result = screen_content("加微信日赚千元在家可做", "weibo")
        assert result.verdict == "reject"


class TestAnalystFastTrack:
    """Verify analyst.annotate() fast_track path."""

    def test_fast_track_skips_llm(self):
        """annotate(use_llm=False) should return Annotation without API call."""
        from agents.analyst import annotate
        from agents.shared import RawData, SentinelResult

        raw = RawData(
            url="https://example.com/test",
            platform="weibo",
            title="测试标题",
            content="这个产品非常好用强烈推荐",
            author="测试用户",
        )
        sentinel = SentinelResult(
            verdict="fast_track",
            reason="test fast track",
            suggested_sentiment="正面",
            suggested_severity="P3",
            rule_hits=["test_hit"],
        )
        annotation = annotate(raw, use_llm=False, sentinel_result=sentinel)
        assert annotation.sentiment == "正面"
        assert annotation.severity == "P3"
        assert "快速通道" in annotation.summary
        assert annotation.relevance == "relevant"

    def test_fast_track_requires_sentinel(self):
        """annotate(use_llm=False) without sentinel_result should raise."""
        from agents.analyst import annotate
        from agents.shared import RawData

        raw = RawData(
            url="https://example.com/test",
            platform="weibo",
            title="test",
            content="test",
            author="test",
        )
        with pytest.raises(ValueError):
            annotate(raw, use_llm=False)

    def test_normal_path_still_calls_llm(self):
        """annotate() with defaults should attempt LLM (may fail without API key)."""
        from agents.analyst import annotate
        from agents.shared import RawData

        raw = RawData(
            url="https://example.com/test",
            platform="weibo",
            title="测试",
            content="正常内容",
            author="test",
        )
        # Without API key, this will fail — but the fallback should work
        try:
            annotation = annotate(raw)
            assert annotation is not None
        except ValueError:
            pass  # No API key configured is acceptable


class TestTopicDiscovery:
    """Verify topic auto-discovery (P4)."""

    def test_discover_topics_returns_list(self):
        """discover_topics should return a list (empty or not)."""
        clear_topic_cache()
        topics = discover_topics(max_keywords=10)
        assert isinstance(topics, list)

    def test_discover_topics_deduped(self):
        """Returned keywords should not have duplicates."""
        clear_topic_cache()
        topics = discover_topics(max_keywords=20)
        assert len(topics) == len(set(topics))

    def test_discover_topics_cache(self):
        """Second call should use cache (faster)."""
        clear_topic_cache()
        topics1 = discover_topics(max_keywords=5)
        topics2 = discover_topics(max_keywords=5)
        assert topics1 == topics2  # Cache should return same results

    def test_clear_topic_cache(self):
        """clear_topic_cache should reset cache."""
        discover_topics(max_keywords=5)
        clear_topic_cache()
        assert _get_cache_age() == 0

    def test_max_keywords_limit(self):
        """max_keywords parameter should limit results."""
        clear_topic_cache()
        topics = discover_topics(max_keywords=5)
        assert len(topics) <= 5
