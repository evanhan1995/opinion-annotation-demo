# -*- coding: utf-8 -*-
"""LLM 降级状态追踪测试：对称 2/2 阈值 + 组件隔离 + 持久化恢复。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.model_degradation as md


def _reset(tmp_path, monkeypatch):
    monkeypatch.setattr(md, "MODEL_DEGRADATION_PATH", tmp_path / "model_degradation.json")
    md._state.clear()


def test_enter_degraded_after_2_failures(tmp_path, monkeypatch):
    """连续 2 次失败进入降级。"""
    _reset(tmp_path, monkeypatch)
    md.record_llm_failure("analyst", "timeout")
    assert md.is_llm_degraded("analyst") is False
    md.record_llm_failure("analyst", "timeout")
    assert md.is_llm_degraded("analyst") is True


def test_one_success_does_not_recover(tmp_path, monkeypatch):
    """降级后 1 次成功不解除（对称 2/2）。"""
    _reset(tmp_path, monkeypatch)
    md.record_llm_failure("analyst", "x")
    md.record_llm_failure("analyst", "x")
    md.record_llm_success("analyst")  # 第 1 次成功
    assert md.is_llm_degraded("analyst") is True


def test_two_successes_recover(tmp_path, monkeypatch):
    """降级后连续 2 次成功解除。"""
    _reset(tmp_path, monkeypatch)
    md.record_llm_failure("analyst", "x")
    md.record_llm_failure("analyst", "x")
    md.record_llm_success("analyst")
    md.record_llm_success("analyst")
    assert md.is_llm_degraded("analyst") is False


def test_component_isolation(tmp_path, monkeypatch):
    """analyst 降级不影响 curator。"""
    _reset(tmp_path, monkeypatch)
    md.record_llm_failure("analyst", "x")
    md.record_llm_failure("analyst", "x")
    assert md.is_llm_degraded("analyst") is True
    assert md.is_llm_degraded("curator") is False
    assert md.get_degraded_components() == ["analyst"]


def test_restart_restores_state(tmp_path, monkeypatch):
    """进程重启后从磁盘恢复降级状态。"""
    _reset(tmp_path, monkeypatch)
    md.record_llm_failure("daily_report", "401")
    md.record_llm_failure("daily_report", "401")
    assert md.is_llm_degraded("daily_report") is True

    # 模拟重启：从磁盘重新加载
    md._state.clear()
    md._state.update(md._load())
    assert md.is_llm_degraded("daily_report") is True
    assert md._state["daily_report"]["last_error"] == "401"
