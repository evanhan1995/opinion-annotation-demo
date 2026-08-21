# -*- coding: utf-8 -*-
"""爬虫降级追踪：持久化 + 不对称滞后 测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agents.orchestrator as orch


def _reset_state(tmp_path, monkeypatch):
    """隔离：config 文件指向 tmp，内存状态清零。"""
    monkeypatch.setattr(orch, "_SCRAPER_DEGRADATION_PATH", tmp_path / "scraper_degradation.json")
    monkeypatch.setattr(orch, "_SCRAPER_FAILURES", {})


def test_three_failures_degrade(tmp_path, monkeypatch):
    """连续失败 3 次 → 降级。"""
    _reset_state(tmp_path, monkeypatch)
    orch.record_scraper_failure("xiaohongshu", "Cookie 过期")
    orch.record_scraper_failure("xiaohongshu", "Cookie 过期")
    assert orch.get_scraper_degraded() == (False, "", "")

    orch.record_scraper_failure("xiaohongshu", "反爬拦截")
    is_degraded, pf, err = orch.get_scraper_degraded()
    assert is_degraded is True
    assert pf == "xiaohongshu"
    assert err == "反爬拦截"


def test_one_success_does_not_undegrade(tmp_path, monkeypatch):
    """降级后 1 次成功不解除。"""
    _reset_state(tmp_path, monkeypatch)
    for _ in range(3):
        orch.record_scraper_failure("xiaohongshu", "Cookie 过期")

    orch.record_scraper_success("xiaohongshu")  # 1 次成功
    is_degraded, _, _ = orch.get_scraper_degraded()
    assert is_degraded is True  # 仍降级


def test_two_successes_undegrade(tmp_path, monkeypatch):
    """降级后连续 2 次成功解除。"""
    _reset_state(tmp_path, monkeypatch)
    for _ in range(3):
        orch.record_scraper_failure("xiaohongshu", "Cookie 过期")

    orch.record_scraper_success("xiaohongshu")  # 第 1 次
    orch.record_scraper_success("xiaohongshu")  # 第 2 次
    assert orch.get_scraper_degraded() == (False, "", "")


def test_restart_restores_state(tmp_path, monkeypatch):
    """进程重启后从磁盘恢复 count 和 last_error。"""
    _reset_state(tmp_path, monkeypatch)
    for _ in range(3):
        orch.record_scraper_failure("xiaohongshu", "Cookie 过期")

    # 模拟重启：重新从磁盘加载
    restored = orch._load_scraper_failures()
    assert restored["xiaohongshu"]["count"] == 3
    assert restored["xiaohongshu"]["last_error"] == "Cookie 过期"

    # 重启后 get_scraper_degraded 依然准确
    monkeypatch.setattr(orch, "_SCRAPER_FAILURES", restored)
    is_degraded, pf, err = orch.get_scraper_degraded()
    assert is_degraded is True
    assert pf == "xiaohongshu"
    assert err == "Cookie 过期"


def test_failure_alternation_no_jitter(tmp_path, monkeypatch):
    """失败/成功交替不应导致状态来回跳（降级后 1 成功 1 失败仍降级）。"""
    _reset_state(tmp_path, monkeypatch)
    for _ in range(3):
        orch.record_scraper_failure("xiaohongshu", "Cookie 过期")

    # 降级后：成功 1 次（不解除），又失败 1 次（successes 清零，count 继续累加）
    orch.record_scraper_success("xiaohongshu")
    orch.record_scraper_failure("xiaohongshu", "网络超时")

    is_degraded, _, err = orch.get_scraper_degraded()
    assert is_degraded is True
    assert err == "网络超时"
