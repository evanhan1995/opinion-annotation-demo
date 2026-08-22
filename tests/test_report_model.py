# -*- coding: utf-8 -*-
"""FinalReport 模型与持久化测试。"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from engine import report_model


def _make_fr(report_type="daily", date="2026-08-19", markdown=None):
    return report_model.FinalReport(
        report_id=f"{report_type}-{date}",
        report_type=report_type,
        report_date=date,
        template_id=f"default-{report_type}",
        template_version=1,
        generated_at="2026-08-19T21:07:00",
        data={"total_new_cases": 30},
        ir={"report_type": report_type, "date": date, "chapters": []},
        markdown=markdown or f"# 舆情{'月报' if report_type == 'monthly' else '日报'} {date}",
        html="<html></html>",
    )


def test_to_from_dict_roundtrip():
    fr = _make_fr()
    d = fr.to_dict()
    fr2 = report_model.FinalReport.from_dict(d)
    assert fr2.report_id == fr.report_id
    assert fr2.markdown == fr.markdown
    assert fr2.chapters() == []


def test_make_report_id():
    assert report_model.make_report_id("daily", "2026-08-19") == "daily-2026-08-19"


def test_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(report_model, "WIKI_DIR", tmp_path)
    fr = _make_fr()
    json_path = report_model.save_final_report(fr)
    assert Path(json_path).exists()
    loaded = report_model.load_final_report("daily", "2026-08-19")
    assert loaded is not None
    assert loaded.markdown == fr.markdown
    assert loaded.template_id == "default-daily"


def test_load_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(report_model, "WIKI_DIR", tmp_path)
    assert report_model.load_final_report("daily", "2099-01-01") is None


def test_regenerate_archives_superseded(tmp_path, monkeypatch):
    """手动重生成同一天：新版本 published 覆盖，旧版本 superseded 存档。"""
    monkeypatch.setattr(report_model, "WIKI_DIR", tmp_path)
    fr1 = _make_fr(markdown="# 舆情日报 2026-08-19 (v1)")
    report_model.save_final_report(fr1)

    fr2 = _make_fr(markdown="# 舆情日报 2026-08-19 (v2)")
    report_model.save_final_report(fr2)

    # 当前 published 是 v2
    loaded = report_model.load_final_report("daily", "2026-08-19")
    assert loaded.markdown.endswith("(v2)")

    # 旧版本归档为 v1，且标 superseded
    archived = tmp_path / "reports" / "daily" / "2026-08-19.v1.report.json"
    assert archived.exists()
    old = report_model.FinalReport.from_dict(json.loads(archived.read_text(encoding="utf-8")))
    assert old.status == "superseded"


def test_save_writes_md_and_html(tmp_path, monkeypatch):
    monkeypatch.setattr(report_model, "WIKI_DIR", tmp_path)
    fr = _make_fr()
    report_model.save_final_report(fr)
    assert (tmp_path / "reports" / "daily" / "2026-08-19.md").exists()
    assert (tmp_path / "reports" / "daily" / "2026-08-19.html").exists()
