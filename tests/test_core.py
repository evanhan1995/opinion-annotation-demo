"""核心测试套件 —— index 更新 / 去重 / 纠偏差异判定。

用法:
    cd D:\Claude code\舆情标注Wiki
    python -m pytest tests\test_core.py -v
"""

import json
import sys
import tempfile
import shutil
from datetime import date
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from engine.index_mgr import (
    _split_table_cells,
    _rebuild_row,
    _upsert_dimension_row,
    update_case_index,
)
from engine.ingestor import _find_existing_case_by_url
from engine.correction_handler import compare_and_decide


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_wiki(tmp_path):
    """Create a minimal wiki/ directory with a realistic index.md."""
    wiki_dir = tmp_path / "wiki"
    cases_dir = wiki_dir / "cases"
    cases_dir.mkdir(parents=True)

    index_content = """---
title: 测试索引
type: index
---

# 案例库

## 案例总览

| [[cases/case-001|001]] | 测试P0 | P0 | 立即处理 | X | 安全 |
| [[cases/case-002|002]] | 测试P2 | P2 | 持续观察 | Reddit | 质量 |

---

## 按维度索引

### 按严重度
| 严重度 | 案例 |
|--------|------|
| P0 | [[cases/case-001|001]] |
| P1 | —（**待添加**） |
| P2 | [[cases/case-002|002]] |
| P3 | — |

### 按分流建议
| 建议 | 案例 |
|------|------|
| 立即处理 | [[cases/case-001|001]] |
| 持续观察 | [[cases/case-002|002]] |
| 可忽略 | — |
| 正面可利用 | — |

### 按平台
| 平台 | 案例 |
|------|------|
| X (Twitter) | [[cases/case-001|001]] |
| Reddit | [[cases/case-002|002]] |
"""

    index_path = cases_dir / "index.md"
    index_path.write_text(index_content, encoding="utf-8")

    # Patch index_mgr.INDEX_PATH to use temp path
    import engine.index_mgr as im
    original = im.INDEX_PATH
    im.INDEX_PATH = index_path
    yield index_path
    im.INDEX_PATH = original


# ═══════════════════════════════════════════════════════════════════════════════
# Test 1: index update (three dimensions + space preservation)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIndexUpdate:
    """Verify update_case_index correctly updates overview + all 3 dimensions."""

    def test_overview_row_appended(self, temp_wiki):
        update_case_index(
            new_filename="case-003.md",
            severity="P2",
            action="持续观察",
            title="新测试案例",
            platform="小红书",
            tags=["质量"],
            source="auto_ingest",
        )
        content = temp_wiki.read_text(encoding="utf-8")
        assert "case-003" in content
        assert "新测试案例" in content

    def test_severity_dimension_updated(self, temp_wiki):
        update_case_index(
            new_filename="case-003.md",
            severity="P2",
            action="持续观察",
            title="新案例",
            platform="小红书",
            tags=["质量"],
            source="auto_ingest",
        )
        content = temp_wiki.read_text(encoding="utf-8")
        # P2 row should now have 2 cases
        assert "[[cases/case-002|002]], [[cases/case-003|003]]" in content

    def test_action_dimension_updated(self, temp_wiki):
        update_case_index(
            new_filename="case-003.md",
            severity="P2",
            action="持续观察",
            title="新案例",
            platform="小红书",
            tags=["质量"],
            source="auto_ingest",
        )
        content = temp_wiki.read_text(encoding="utf-8")
        assert "[[cases/case-002|002]], [[cases/case-003|003]]" in content

    def test_platform_dimension_updated(self, temp_wiki):
        update_case_index(
            new_filename="case-003.md",
            severity="P2",
            action="持续观察",
            title="新案例",
            platform="小红书",
            tags=["质量"],
            source="auto_ingest",
        )
        content = temp_wiki.read_text(encoding="utf-8")
        assert "小红书" in content
        assert "[[cases/case-003|003]]" in content

    def test_placeholder_replaced(self, temp_wiki):
        """P1 row with placeholder should be replaced, not appended."""
        update_case_index(
            new_filename="case-003.md",
            severity="P1",
            action="持续观察",
            title="新P1案例",
            platform="小红书",
            tags=["合规"],
            source="auto_ingest",
        )
        content = temp_wiki.read_text(encoding="utf-8")
        assert "[[cases/case-003|003]]" in content
        assert "**待添加**" not in content

    def test_space_preservation(self, temp_wiki):
        """Wiki links should retain proper table spacing."""
        update_case_index(
            new_filename="case-003.md",
            severity="P2",
            action="持续观察",
            title="新案例",
            platform="小红书",
            tags=["质量"],
            source="auto_ingest",
        )
        content = temp_wiki.read_text(encoding="utf-8")
        # Correct: space after | and space before |
        assert "| P2 | [[cases/case-002|002]], [[cases/case-003|003]] |" in content

    def test_human_correction_format(self, temp_wiki):
        """Correction cases should use the right row format."""
        update_case_index(
            new_filename="case-003.md",
            severity="P2",
            action="立即处理",
            title="纠偏测试案例",
            platform="—",
            tags=["纠偏案例"],
            source="human_correction",
        )
        content = temp_wiki.read_text(encoding="utf-8")
        assert "纠偏案例" in content
        today = date.today().isoformat()
        assert today in content

    def test_no_duplicate_case_ref(self, temp_wiki):
        """Calling update twice with same case should not duplicate refs."""
        update_case_index(
            new_filename="case-003.md",
            severity="P2",
            action="持续观察",
            title="新案例",
            platform="小红书",
            tags=["质量"],
            source="auto_ingest",
        )
        # Second call with same case should be a no-op in dimension rows
        update_case_index(
            new_filename="case-003.md",
            severity="P2",
            action="持续观察",
            title="新案例",
            platform="小红书",
            tags=["质量"],
            source="auto_ingest",
        )
        content = temp_wiki.read_text(encoding="utf-8")
        # case-003 should appear exactly once in the dimension rows
        # (overview table may have it twice, which is a separate concern)
        severity_section = content.split("### 按严重度")[1].split("### 按分流建议")[0]
        assert severity_section.count("case-003") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2: dedup (frontmatter URL matching)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDedup:
    """Verify frontmatter-based URL dedup."""

    @pytest.fixture
    def temp_cases(self, tmp_path):
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir(parents=True)
        # Create a case with url in frontmatter
        case_content = """---
title: 测试案例
type: case
url: https://www.xiaohongshu.com/explore/test123
---
正文内容
"""
        (cases_dir / "case-001.md").write_text(case_content, encoding="utf-8")
        return cases_dir

    def test_url_match_found(self, monkeypatch, temp_cases):
        """Known URL should return the case filename."""
        # Redirect CASES_DIR to temp dir
        import engine.ingestor as ing
        original = ing.CASES_DIR
        ing.CASES_DIR = temp_cases
        try:
            result = ing._find_existing_case_by_url(
                "https://www.xiaohongshu.com/explore/test123"
            )
            assert result == "case-001.md"
        finally:
            ing.CASES_DIR = original

    def test_url_not_found(self, monkeypatch, temp_cases):
        """Unknown URL should return None."""
        import engine.ingestor as ing
        original = ing.CASES_DIR
        ing.CASES_DIR = temp_cases
        try:
            result = ing._find_existing_case_by_url(
                "https://www.youtube.com/watch?v=unknown"
            )
            assert result is None
        finally:
            ing.CASES_DIR = original

    def test_empty_url(self, monkeypatch, temp_cases):
        """Empty URL should return None immediately."""
        import engine.ingestor as ing
        original = ing.CASES_DIR
        ing.CASES_DIR = temp_cases
        try:
            result = ing._find_existing_case_by_url("")
            assert result is None
        finally:
            ing.CASES_DIR = original

    def test_url_not_in_frontmatter_but_in_body(self, monkeypatch, tmp_path):
        """URL in body but not in frontmatter should NOT match."""
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir(parents=True)
        case_content = """---
title: 无URL案例
type: case
---
链接：https://www.youtube.com/watch?v=bodyonly
"""
        (cases_dir / "case-002.md").write_text(case_content, encoding="utf-8")
        import engine.ingestor as ing
        original = ing.CASES_DIR
        ing.CASES_DIR = cases_dir
        try:
            result = ing._find_existing_case_by_url(
                "https://www.youtube.com/watch?v=bodyonly"
            )
            assert result is None, "URL in body should not match frontmatter scan"
        finally:
            ing.CASES_DIR = original


# ═══════════════════════════════════════════════════════════════════════════════
# Test 3: correction diff level
# ═══════════════════════════════════════════════════════════════════════════════

class TestCorrectionDiff:
    """Verify compare_and_decide correctly classifies diff levels."""

    def test_significant_severity_change(self):
        ai = {"严重度评级": "P2", "分流建议": "持续观察", "摘要": "测试"}
        human = {"严重度评级": "P1", "分流建议": "持续观察", "摘要": "测试"}
        level, diffs = compare_and_decide(ai, human)
        assert level == "significant"
        assert "严重度评级" in diffs

    def test_significant_action_change(self):
        ai = {"严重度评级": "P2", "分流建议": "持续观察", "摘要": "测试"}
        human = {"严重度评级": "P2", "分流建议": "立即处理", "摘要": "测试"}
        level, diffs = compare_and_decide(ai, human)
        assert level == "significant"
        assert "分流建议" in diffs

    def test_minor_sentiment_change(self):
        """情感分析变化（非严重度/分流）应判定为 minor。"""
        ai = {
            "严重度评级": "P2",
            "分流建议": "持续观察",
            "情感分析": {"整体情感": "负面"},
        }
        human = {
            "严重度评级": "P2",
            "分流建议": "持续观察",
            "情感分析": {"整体情感": "中性"},
        }
        level, diffs = compare_and_decide(ai, human)
        assert level == "minor"
        assert "情感分析.整体情感" in diffs

    def test_no_change(self):
        ai = {"严重度评级": "P2", "分流建议": "持续观察", "摘要": "一样"}
        human = {"严重度评级": "P2", "分流建议": "持续观察", "摘要": "一样"}
        level, diffs = compare_and_decide(ai, human)
        assert level == "none"


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests for table helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestSplitTableCells:
    """Verify Wiki link protection during table split."""

    def test_split_preserves_wikilink(self):
        row = "| P2 | [[cases/case-002|002]], [[cases/case-007|007]] |"
        parts = _split_table_cells(row)
        assert len(parts) >= 3
        assert "[[cases/case-002|002]]" in parts[2]
        assert "[[cases/case-007|007]]" in parts[2]

    def test_roundtrip(self):
        original = "| P2 | [[cases/case-002|002]] |"
        rebuilt = _rebuild_row(_split_table_cells(original))
        assert rebuilt == original

    def test_upsert_appends_correctly(self):
        row = "| P2 | [[cases/case-002|002]], [[cases/case-007|007]] |"
        result = _upsert_dimension_row(row, "P2", "[[cases/case-012|012]]")
        assert "case-012" in result
        assert result.startswith("| P2 | ")

    def test_upsert_replaces_placeholder(self):
        row = "| P1 | —（**待添加**） |"
        result = _upsert_dimension_row(row, "P1", "[[cases/case-010|010]]")
        assert "case-010" in result
        assert "**待添加**" not in result
        assert result == "| P1 | [[cases/case-010|010]] |"

    def test_upsert_no_duplicate(self):
        row = "| P2 | [[cases/case-002|002]], [[cases/case-003|003]] |"
        result = _upsert_dimension_row(row, "P2", "[[cases/case-003|003]]")
        assert result == row
