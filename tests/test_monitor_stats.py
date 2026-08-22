# -*- coding: utf-8 -*-
"""monitor_stats 持久化 / 读取 / 月度聚合 测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agents.monitor as monitor
import agents.daily_report as dr
from agents.monitor import MonitorStats


def _reset_outputs(tmp_path, monkeypatch):
    """把 OUTPUTS_DIR 指向临时目录，隔离文件系统。"""
    monkeypatch.setattr(monitor, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(dr, "OUTPUTS_DIR", tmp_path)


def test_persist_and_load_roundtrip(tmp_path, monkeypatch):
    """持久化 → 读取 往返：字段一致。"""
    _reset_outputs(tmp_path, monkeypatch)
    stats = MonitorStats(
        keywords_searched=3, platforms_queried=9,
        total_fetched=100, total_new=30, dedup_rate=0.7,
    )
    monitor._persist_monitor_stats(stats, "2026-08-21", ["kw1", "kw2", "kw3"])

    path = tmp_path / "monitor_stats_2026-08-21.json"
    assert path.exists()

    loaded = dr._load_daily_monitor_stats("2026-08-21")
    assert loaded == {"监测关键词数": 3, "去重率": 0.7}


def test_load_daily_no_file(tmp_path, monkeypatch):
    """当天无文件 → 返回空 dict（=无监测数据），而不是 0。"""
    _reset_outputs(tmp_path, monkeypatch)
    assert dr._load_daily_monitor_stats("2026-08-21") == {}


def test_aggregate_monthly(tmp_path, monkeypatch):
    """月度聚合：关键词去重 + 去重率重新计算（不对每日 rate 平均）。"""
    _reset_outputs(tmp_path, monkeypatch)

    day1 = MonitorStats(keywords_searched=2, platforms_queried=4,
                        total_fetched=100, total_new=40, dedup_rate=0.6)
    day2 = MonitorStats(keywords_searched=2, platforms_queried=4,
                        total_fetched=200, total_new=50, dedup_rate=0.75)

    # kw2 两天重复，去重后应为 {kw1, kw2, kw3} = 3
    monitor._persist_monitor_stats(day1, "2026-08-01", ["kw1", "kw2"])
    monitor._persist_monitor_stats(day2, "2026-08-02", ["kw2", "kw3"])

    agg = dr._aggregate_monthly_monitor_stats("2026-08")
    assert agg["监测关键词数"] == 3
    # (100+200 - 40 - 50) / (100+200) = 210 / 300 = 0.7
    assert abs(agg["去重率"] - 0.7) < 1e-9


def test_aggregate_monthly_no_files(tmp_path, monkeypatch):
    """当月无文件 → 空 dict。"""
    _reset_outputs(tmp_path, monkeypatch)
    assert dr._aggregate_monthly_monitor_stats("2026-08") == {}


def test_monitor_section_no_data():
    """空 dict → 显示「无监测数据」，不显示关键词数。"""
    md = dr._monitor_section_md({})
    assert "无监测数据" in md
    assert "监测关键词数" not in md


def test_monitor_section_with_data():
    """非空 → 真实数字 + 去重率百分比格式。"""
    md = dr._monitor_section_md({"监测关键词数": 3, "去重率": 0.7})
    assert "监测关键词数：3" in md
    assert "去重率：70%" in md


def test_collect_report_data_zero_cases_with_monitor(tmp_path, monkeypatch):
    """0 案例 + Monitor 跑过（stats 文件存在）→ 日报仍生成，含真实监测概况。

    验证「无案例早退」不会跳过 monitor_stats：即使当天案例库 0 条，
    只要 Monitor 跑过，日报的监测概况仍展示真实数字而非「无监测数据」。
    """
    _reset_outputs(tmp_path, monkeypatch)

    # mock curator（当天 0 案例）
    import agents.curator as curator
    monkeypatch.setattr(curator, "query_stats", lambda **kw: {
        "total_cases": 0, "severity_dist": {}, "sentiment_dist": {},
        "platform_dist": {}, "status_dist": {}, "p0_p1_list": [], "top_categories": [],
    })
    monkeypatch.setattr(curator, "query_cases", lambda *a, **kw: [])

    # 模拟 Monitor 跑过，持久化真实统计
    stats = MonitorStats(keywords_searched=5, platforms_queried=15,
                         total_fetched=200, total_new=60, dedup_rate=0.7)
    monitor._persist_monitor_stats(stats, "2026-08-21", ["kw1", "kw2", "kw3", "kw4", "kw5"])

    data = dr._collect_report_data("2026-08-21")

    # 0 案例 → 案例字段为默认 0，但 monitor_stats 为真实数据（未被早退跳过）
    assert data.total_new_cases == 0
    assert data.monitor_stats == {"监测关键词数": 5, "去重率": 0.7}

    # 生成的日报监测概况应展示真实数字
    md = dr._monitor_section_md(data.monitor_stats)
    assert "监测关键词数：5" in md
    assert "去重率：70%" in md
