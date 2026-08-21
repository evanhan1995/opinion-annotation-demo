# -*- coding: utf-8 -*-
"""case_id 生成唯一性测试 —— 覆盖同一秒连续调用 + 多线程并发，断言无碰撞。"""
import io
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pytest

import engine.ingestor as ingestor


def _reset_id_state(tmp_path, monkeypatch):
    """隔离测试环境：把 CASES_DIR 指向空临时目录，并重置进程内预留计数器（None=未播种）。"""
    monkeypatch.setattr(ingestor, "CASES_DIR", tmp_path)
    monkeypatch.setattr(ingestor, "_case_id_reserved", None)


def test_sequential_100_calls_unique(tmp_path, monkeypatch):
    """同一秒内连续调用 100 次，case_id 全部唯一且格式正确。"""
    _reset_id_state(tmp_path, monkeypatch)
    ids = [ingestor.get_next_case_id() for _ in range(100)]
    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert all(i.startswith("case-") for i in ids)


def test_concurrent_calls_unique(tmp_path, monkeypatch):
    """多线程并发调用 200 次，case_id 不碰撞（覆盖 ThreadPoolExecutor 场景）。"""
    _reset_id_state(tmp_path, monkeypatch)
    n = 200
    with ThreadPoolExecutor(max_workers=16) as pool:
        ids = list(pool.map(lambda _: ingestor.get_next_case_id(), range(n)))
    assert len(ids) == n
    assert len(set(ids)) == n


def test_respects_existing_files(tmp_path, monkeypatch):
    """基于已有 case 文件（含平台子目录）递增，不重复分配已占用编号。"""
    _reset_id_state(tmp_path, monkeypatch)
    (tmp_path / "case-007.md").write_text("", encoding="utf-8")
    sub = tmp_path / "douyin"
    sub.mkdir()
    (sub / "case-012.md").write_text("", encoding="utf-8")

    assert ingestor.get_next_case_id() == "case-013"


def test_pipeline_action_plan_matches_case_file(tmp_path, monkeypatch):
    """一次 pipeline 中 ActionPlan.case_id 与最终落盘文件名一致（不占号不落盘）。

    验证 Orchestrator 只生成一次 case_id 并同时传给 triage 与 ingest，
    避免 triage 自行生成导致 ActionPlan.case_id 与入库文件 id 不一致。
    """
    import engine.index_mgr as idxmgr
    import agents.scraper as scraper_mod
    import agents.analyst as analyst_mod
    import agents.sentinel as sentinel_mod
    import agents.curator as curator_mod
    import agents.orchestrator as orch
    from agents.shared import RawData, Annotation

    # 隔离文件系统写入（ingestor 与 curator 各自的路径都指向 tmp，避免污染真实 wiki/）
    cases = tmp_path / "cases"
    cases.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ingestor, "CASES_DIR", cases)
    monkeypatch.setattr(ingestor, "INDEX_PATH", tmp_path / "index.md")
    monkeypatch.setattr(ingestor, "GLOBAL_INDEX_PATH", tmp_path / "global_index.md")
    monkeypatch.setattr(ingestor, "LOG_PATH", tmp_path / "ing_log.md")
    monkeypatch.setattr(ingestor, "RAW_CASES_DIR", tmp_path / "raw_cases")
    monkeypatch.setattr(ingestor, "RAW_ARCHIVE_DIR", tmp_path / "raw_archive")
    monkeypatch.setattr(ingestor, "AUTHORS_DIR", tmp_path / "authors")
    monkeypatch.setattr(ingestor, "_case_id_reserved", None)
    monkeypatch.setattr(curator_mod, "CASES_DIR", cases)
    monkeypatch.setattr(curator_mod, "LOG_PATH", tmp_path / "curator_log.md")
    (tmp_path / "global_index.md").write_text("", encoding="utf-8")
    monkeypatch.setattr(idxmgr, "update_case_index", lambda **kw: None)

    # Mock scraper / analyst / sentinel，避免真实联网与 LLM 调用
    raw = RawData(url="https://example.com/fresh", platform="weibo",
                  title="测试标题", content="测试内容")
    monkeypatch.setattr(scraper_mod, "fetch", lambda url: raw)
    monkeypatch.setattr(scraper_mod, "detect_platform", lambda url: "weibo")
    ann = Annotation(url="https://example.com/fresh", platform="weibo",
                     severity="P2", severity_reason="r", sentiment="负面",
                     risk_tags=["质量"], triage="持续观察", comment_risk="黄",
                     summary="测试摘要")
    monkeypatch.setattr(analyst_mod, "annotate", lambda raw, **kw: ann)
    monkeypatch.setattr(sentinel_mod, "screen_content", lambda content, platform: None)

    result = orch.run_passive_analysis("https://example.com/fresh")

    assert result.action_plan is not None, f"action_plan 为空: {result.errors}"
    assert result.kb_entry is not None, f"kb_entry 为空: {result.errors}"
    assert result.action_plan.case_id == result.kb_entry.case_id, (
        f"ActionPlan.case_id={result.action_plan.case_id} != kb_entry.case_id={result.kb_entry.case_id}"
    )

    # 文件确实落盘，且文件名与 case_id 一致
    found = list(cases.rglob(f"{result.kb_entry.case_id}.md"))
    assert found, f"未找到落盘文件 {result.kb_entry.case_id}.md"
