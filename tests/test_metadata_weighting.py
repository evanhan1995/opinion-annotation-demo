# -*- coding: utf-8 -*-
"""RAG 检索元数据加权测试 —— normalize_platform / 查询关键词识别 / 加权重排 / 回归。"""

import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import engine.agent as agent_mod
from engine.constants import normalize_platform


def _case(path, severity, platform, score, dirname="cases"):
    """构造一条 search_wiki 结果 dict（含 frontmatter）。"""
    return {
        "path": path,
        "title": path,
        "type": "case",
        "dirname": dirname,
        "excerpt": "",
        "score": score,
        "content": "",
        "frontmatter": {"severity": severity, "platform": platform},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# normalize_platform
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizePlatform:
    def test_english_key_to_chinese(self):
        assert normalize_platform("douyin") == "抖音"
        assert normalize_platform("wechat") == "微信公众号"
        assert normalize_platform("bilibili") == "B站"
        assert normalize_platform("weibo") == "微博"
        assert normalize_platform("xiaohongshu") == "小红书"
        assert normalize_platform("youtube") == "YouTube"

    def test_chinese_passthrough(self):
        assert normalize_platform("抖音") == "抖音"
        assert normalize_platform("微信公众号") == "微信公众号"
        assert normalize_platform("B站") == "B站"
        assert normalize_platform("微博") == "微博"
        assert normalize_platform("小红书") == "小红书"

    def test_empty_and_none(self):
        assert normalize_platform("") == ""
        assert normalize_platform(None) is None


# ═══════════════════════════════════════════════════════════════════════════════
# 查询关键词识别
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectQuerySeverities:
    def test_detects_upper(self):
        assert agent_mod._detect_query_severities("抖音 P1 案例") == {"P1"}

    def test_case_insensitive(self):
        assert agent_mod._detect_query_severities("p0 案例") == {"P0"}

    def test_no_severity(self):
        assert agent_mod._detect_query_severities("抖音案例情况") == set()


class TestDetectQueryPlatforms:
    def test_chinese(self):
        assert agent_mod._detect_query_platforms("抖音案例") == {"抖音"}

    def test_english(self):
        assert agent_mod._detect_query_platforms("douyin 案例") == {"抖音"}

    def test_multiple(self):
        assert agent_mod._detect_query_platforms("抖音和微博的对比") == {"抖音", "微博"}

    def test_no_platform(self):
        assert agent_mod._detect_query_platforms("案例情况汇总") == set()


# ═══════════════════════════════════════════════════════════════════════════════
# _weight_search_results
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightSearchResults:
    def test_platform_boost_reorders(self):
        results = [
            _case("c_douyin", "P3", "抖音", 60),
            _case("c_weibo", "P3", "微博", 70),
        ]
        weighted = agent_mod._weight_search_results("抖音案例", results)
        assert weighted[0]["path"] == "c_douyin"  # 同平台案例被提上来

    def test_platform_english_alias_boost(self):
        # 结果里是英文 platform 写法，查询用中文，仍应命中（归一化）
        results = [
            _case("c_douyin", "P3", "douyin", 60),
            _case("c_weibo", "P3", "weibo", 70),
        ]
        weighted = agent_mod._weight_search_results("抖音案例", results)
        assert weighted[0]["path"] == "c_douyin"

    def test_severity_boost_reorders(self):
        results = [
            _case("c_p1", "P1", "微博", 60),
            _case("c_p3", "P3", "微博", 70),
        ]
        weighted = agent_mod._weight_search_results("P1 案例", results)
        assert weighted[0]["path"] == "c_p1"

    def test_combined_boost_is_strongest(self):
        # 抖音+P1 都命中 → ×1.3×1.3，应排最前
        results = [
            _case("c_other", "P3", "微博", 60),
            _case("c_douyin_p3", "P3", "抖音", 60),
            _case("c_douyin_p1", "P1", "抖音", 60),
        ]
        weighted = agent_mod._weight_search_results("抖音 P1 案例", results)
        assert weighted[0]["path"] == "c_douyin_p1"

    def test_non_case_not_weighted(self):
        # 非 cases 结果（概念页等）不应被加权
        concept = _case("concept_x", "P1", "抖音", 60, dirname="concepts")
        case = _case("c_weibo", "P3", "微博", 60)
        results = [concept, case]
        weighted = agent_mod._weight_search_results("抖音案例", results)
        concept_after = next(r for r in weighted if r["path"] == "concept_x")
        assert concept_after["score"] == 60  # 概念页分数不变

    def test_irrelevant_case_not_pushed_to_top(self):
        # 弱相关但同平台(5) 不应挤掉 强相关异平台(80)
        results = [
            _case("c_irrelevant_douyin", "P3", "抖音", 5),
            _case("c_relevant_weibo", "P3", "微博", 80),
        ]
        weighted = agent_mod._weight_search_results("抖音案例", results)
        assert weighted[0]["path"] == "c_relevant_weibo"

    def test_no_keyword_returns_unchanged(self):
        # 回归：无平台/严重度关键词 → 返回原列表（顺序与分数完全不变）
        results = [
            _case("c_a", "P3", "微博", 70),
            _case("c_b", "P1", "抖音", 60),
        ]
        weighted = agent_mod._weight_search_results("知识库里有哪些案例", results)
        assert weighted is results  # 早退返回同一对象
        assert [r["score"] for r in weighted] == [70, 60]


# ═══════════════════════════════════════════════════════════════════════════════
# search_wiki 集成：确认加权接在两条路径上
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchWikiWeighting:
    def test_embedding_path_weighted(self, monkeypatch):
        monkeypatch.setattr(agent_mod, "_embedding_search", lambda q, n: [
            _case("c_douyin", "P3", "抖音", 60),
            _case("c_weibo", "P3", "微博", 70),
        ])
        results = agent_mod.search_wiki("抖音案例", max_results=5)
        assert results[0]["path"] == "c_douyin"

    def test_bigram_fallback_path_weighted(self, monkeypatch):
        monkeypatch.setattr(agent_mod, "_embedding_search", lambda q, n: None)
        monkeypatch.setattr(agent_mod, "_bigram_search", lambda q, n: [
            _case("c_p1", "P1", "微博", 60),
            _case("c_p3", "P3", "微博", 70),
        ])
        results = agent_mod.search_wiki("P1 案例", max_results=5)
        assert results[0]["path"] == "c_p1"

    def test_no_keyword_search_unchanged(self, monkeypatch):
        monkeypatch.setattr(agent_mod, "_embedding_search", lambda q, n: [
            _case("c_a", "P3", "微博", 70),
            _case("c_b", "P1", "抖音", 60),
        ])
        results = agent_mod.search_wiki("知识库情况", max_results=5)
        assert [r["score"] for r in results] == [70, 60]
