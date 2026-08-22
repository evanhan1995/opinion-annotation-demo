# -*- coding: utf-8 -*-
"""Monitor 关键词配置保存保护测试：防误清空逻辑。"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui import tab3_monitor as t3


def _write(path: Path, keywords: list):
    path.write_text(
        json.dumps({"keywords": keywords, "defaults": {"result_count": 30}},
                   ensure_ascii=False),
        encoding="utf-8",
    )


def test_block_when_empty_and_disk_nonempty(tmp_path):
    """空列表 + 磁盘已有非空配置 → 拦截写入，文件不变。"""
    p = tmp_path / "monitor_keywords.json"
    _write(p, [{"id": "kw001", "keyword": "字节避雷", "active": True}])
    before = p.read_text(encoding="utf-8")

    result = t3._save_keywords_config(p, {"keywords": [], "defaults": {"result_count": 30}})

    assert result is False
    assert p.read_text(encoding="utf-8") == before  # 未写入


def test_allow_when_empty_and_disk_empty(tmp_path):
    """空列表 + 磁盘本就空 → 允许写入空列表（不拦截合理清空）。"""
    p = tmp_path / "monitor_keywords.json"
    _write(p, [])

    result = t3._save_keywords_config(p, {"keywords": [], "defaults": {"result_count": 30}})

    assert result is True
    assert json.loads(p.read_text(encoding="utf-8"))["keywords"] == []


def test_allow_when_file_missing(tmp_path):
    """文件不存在 → 允许写入空列表。"""
    p = tmp_path / "monitor_keywords.json"
    assert not p.exists()

    result = t3._save_keywords_config(p, {"keywords": [], "defaults": {"result_count": 30}})

    assert result is True
    assert p.exists()


def test_allow_when_nonempty(tmp_path):
    """非空列表 → 正常写入。"""
    p = tmp_path / "monitor_keywords.json"
    _write(p, [{"id": "kw001", "keyword": "旧词", "active": True}])

    cfg = {"keywords": [{"id": "kw001", "keyword": "新词", "active": True}],
           "defaults": {"result_count": 30}}
    result = t3._save_keywords_config(p, cfg)

    assert result is True
    assert json.loads(p.read_text(encoding="utf-8"))["keywords"][0]["keyword"] == "新词"


def test_warning_logged_on_block(tmp_path, caplog):
    """拦截时记录 warning 日志（非静默）。"""
    p = tmp_path / "monitor_keywords.json"
    _write(p, [{"id": "kw001", "keyword": "a", "active": True}])

    with caplog.at_level(logging.WARNING, logger="yuqing"):
        t3._save_keywords_config(p, {"keywords": [], "defaults": {"result_count": 30}})

    assert any("拦截" in r.message for r in caplog.records)
