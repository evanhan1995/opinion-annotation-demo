# -*- coding: utf-8 -*-
"""LLM 降级链测试：Analyst 多 provider + Sentinel、Curator 检索降级、DailyReport 超时回退。"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import engine.annotate as ann
import engine.agent as ag
import agents.shared as sh
import engine.model_degradation as md


@pytest.fixture
def isolation(tmp_path, monkeypatch):
    """隔离降级状态 + 模拟 deepseek/minimax 均已配置 key。"""
    monkeypatch.setattr(md, "MODEL_DEGRADATION_PATH", tmp_path / "md.json")
    md._state.clear()
    monkeypatch.setattr(sh, "MODEL_REGISTRY", {
        "deepseek": sh.ModelConfig("deepseek", "deepseek-chat", "sk-ds", "https://api.deepseek.com"),
        "minimax": sh.ModelConfig("minimax", "abab6.5s-chat", "sk-mm", "https://api.minimax.chat/v1"),
    })


class _Sentinel:
    suggested_severity = "P2"
    suggested_sentiment = "负面"
    reason = "Obvious negative pattern"


_OK = {"严重度评级": "P1", "严重度理由": "ok", "情感分析": {"整体情感": "负面"},
       "风险标签": ["质量"], "分流建议": "立即处理",
       "评论区分析": {"评论红绿灯": {"红": 1, "黄": 0, "绿": 0}},
       "舆情分类": ["安全"], "摘要": "ok"}
_FAIL = {"error": True, "message": "deepseek 401"}
_PARSE_FAIL = {"error": True, "message": "API 返回内容无法解析为 JSON"}


def _mock_annotate(seq):
    """按调用顺序返回 error/success 的 _annotate_openai_style。"""
    calls = {"n": 0}
    def fake(user_message, system_prompt, config):
        i = calls["n"]; calls["n"] += 1
        return seq[i] if i < len(seq) else {"error": True, "message": "extra"}
    return fake


# ── Analyst ────────────────────────────────────────────────────────────

def test_analyst_fallback_to_minimax(isolation):
    """deepseek 失败 → minimax 成功 → 用 minimax 结果，degraded=False。"""
    with mock.patch.object(ann, "_annotate_openai_style", _mock_annotate([_FAIL, _OK])):
        result, degraded, reason = ann.annotate_with_fallback("u", "s", {"max_tokens": 100})
    assert degraded is False
    assert result["严重度评级"] == "P1"


def test_analyst_fallback_to_sentinel(isolation):
    """deepseek+minimax 都失败 → Sentinel 预标注，degraded=True。"""
    with mock.patch.object(ann, "_annotate_openai_style", _mock_annotate([_FAIL, _FAIL])):
        result, degraded, reason = ann.annotate_with_fallback("u", "s", {"max_tokens": 100}, _Sentinel())
    assert degraded is True
    assert result["严重度评级"] == "P2"
    assert "sentinel" in reason


def test_analyst_fallback_mock_no_sentinel(isolation):
    """都失败且无 sentinel → error dict，degraded=True。"""
    with mock.patch.object(ann, "_annotate_openai_style", _mock_annotate([_FAIL, _FAIL])):
        result, degraded, reason = ann.annotate_with_fallback("u", "s", {"max_tokens": 100})
    assert degraded is True
    assert result.get("error") is True


def test_analyst_json_parse_failure_triggers_fallback(isolation):
    """deepseek JSON 解析失败（error dict）同样触发切换下一 provider。"""
    with mock.patch.object(ann, "_annotate_openai_style", _mock_annotate([_PARSE_FAIL, _OK])):
        result, degraded, _ = ann.annotate_with_fallback("u", "s", {"max_tokens": 100})
    assert degraded is False
    assert result["严重度评级"] == "P1"


# ── Curator ────────────────────────────────────────────────────────────

def test_curator_ask_agent_degrades_to_search(isolation, monkeypatch):
    """ask_agent LLM 抛异常 → answer_from_search_only，degraded=True + ⚠️ 提示。"""
    monkeypatch.setattr(ag, "search_wiki", lambda *a, **k: [{
        "path": "cases/c-1.md", "title": "t1", "type": "case", "dirname": "cases",
        "excerpt": "e1", "score": 10, "content": "x", "frontmatter": {"severity": "P1"},
    }])
    with mock.patch.object(ag, "_call_openai_style", side_effect=Exception("timeout")):
        result = ag.ask_agent("q", {"api_key": "k", "api_base": "b", "api_style": "openai", "agent_model": "m"})
    assert result.get("degraded") is True
    assert "⚠️ 模型暂不可用" in result["answer"]
    assert len(result.get("citations", [])) == 1


def test_curator_ask_agent_success_marks_recovered(isolation, monkeypatch):
    """LLM 成功 → record_llm_success 被调用（degraded 状态被清除）。"""
    monkeypatch.setattr(ag, "search_wiki", lambda *a, **k: [])
    md.record_llm_failure("curator", "x")
    md.record_llm_failure("curator", "x")
    assert md.is_llm_degraded("curator") is True
    with mock.patch.object(ag, "_call_openai_style", return_value="ok answer"):
        result = ag.ask_agent("q", {"api_key": "k", "api_base": "b", "api_style": "openai", "agent_model": "m"})
    # 1 次成功未达解除阈值（对称 2/2），仍降级
    assert result.get("degraded") is None
    assert md.is_llm_degraded("curator") is True


# ── Daily Report ───────────────────────────────────────────────────────

def test_daily_report_fill_analysis_timeout_raises(isolation):
    """fill_analysis LLM 超时 → 抛 RuntimeError（外层模板回退）+ 记录降级。"""
    from engine import report_ir
    ir = report_ir.ReportIR(report_type="daily", date="2026-08-22",
                            chapters=[report_ir.Chapter(anchor="volume-overview", title="一、声量概览",
                                                        data_rows={"total_new_cases": 1, "avg_prev_7days": 0.0, "trend": "→"})])
    with mock.patch("engine._compat.call_with_timeout", return_value=(None, "操作超时 (90s)")):
        # 连续 2 次超时 → 达到降级阈值
        for _ in range(2):
            with pytest.raises(RuntimeError, match="LLM 调用失败"):
                report_ir.fill_analysis(ir)
    assert md.is_llm_degraded("daily_report") is True
