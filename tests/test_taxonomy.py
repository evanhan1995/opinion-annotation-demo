# -*- coding: utf-8 -*-
"""Phase 1 taxonomy 模块测试 —— 词表加载/校验/候选/CRUD/Agent搜索扩展。

用法:
    python -m pytest tests/test_taxonomy.py -v
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from engine.taxonomy_mgr import (
    Taxonomy,
    TaxonomyNode,
    load_taxonomy,
    load_taxonomy_cached,
    validate_tags,
    limit_tags,
    suggest_candidates,
    approve_candidate,
    reject_candidate,
    build_taxonomy_prompt_section,
    add_l2_node,
    remove_l2_node,
    add_l1_node,
    _load_candidates,
    _save_candidates,
    _reload_cache,
    _serialize_taxonomy_nodes,
    _parse_taxonomy_body,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Taxonomy loading & parsing
# ═══════════════════════════════════════════════════════════════════════════════

class TestTaxonomyLoad:
    """Verify taxonomy files load correctly from wiki/taxonomy/."""

    def test_load_narrative_categories(self):
        nt = load_taxonomy("narrative_categories")
        assert nt.taxonomy_type == "narrative_category"
        assert nt.version >= 1
        assert len(nt.nodes) >= 5  # at least 5 L1s
        assert all(isinstance(n, TaxonomyNode) for n in nt.nodes)

    def test_load_risk_tags(self):
        rt = load_taxonomy("risk_tags")
        assert rt.taxonomy_type == "risk_tag"
        assert len(rt.nodes) >= 3
        # Risk tags should have children
        total_l2 = sum(len(n.children) for n in rt.nodes)
        assert total_l2 >= 10

    def test_load_disposition_actions(self):
        da = load_taxonomy("disposition_actions")
        assert da.taxonomy_type == "disposition_action"
        assert len(da.nodes) >= 3

    def test_flat_labels_narrative(self):
        nt = load_taxonomy("narrative_categories")
        labels = nt.flat_labels()
        assert len(labels) >= 15
        # All labels should be in L1/L2 format
        for label in labels:
            assert "/" in label, f"Expected L1/L2 format, got: {label}"

    def test_flat_labels_risk_tags(self):
        rt = load_taxonomy("risk_tags")
        labels = rt.flat_labels()
        assert len(labels) >= 10
        # Flat labels should NOT have "/"
        for label in labels:
            assert "/" not in label, f"Expected flat label, got: {label}"

    def test_label_set(self):
        nt = load_taxonomy("narrative_categories")
        ls = nt.label_set()
        assert isinstance(ls, set)
        # Should contain lowercased versions
        for label in nt.flat_labels():
            assert label.lower() in ls

    def test_find_node(self):
        nt = load_taxonomy("narrative_categories")
        labels = nt.flat_labels()
        if labels:
            node = nt.find_node(labels[0])
            assert node is not None
            assert node.name  # should have a name

    def test_find_node_not_found(self):
        nt = load_taxonomy("narrative_categories")
        node = nt.find_node("不存在/不存在")
        assert node is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tag validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestTagValidation:
    """Verify tag validation against word lists."""

    def test_valid_tags_pass(self):
        rt = load_taxonomy("risk_tags")
        valid = rt.flat_labels()[:2]
        result = validate_tags(valid, rt)
        # Tags in the taxonomy go into "valid" list
        assert len(result["valid"]) == 2
        assert len(result["candidates"]) == 0

    def test_candidate_detection(self):
        rt = load_taxonomy("risk_tags")
        result = validate_tags(["完全不存在的标签XYZ"], rt)
        assert len(result["valid"]) == 0
        assert len(result["candidates"]) == 1
        assert "完全不存在的标签XYZ" in result["candidates"]

    def test_mixed_valid_and_candidate(self):
        rt = load_taxonomy("risk_tags")
        valid_label = rt.flat_labels()[0]
        result = validate_tags([valid_label, "新标签ABC"], rt)
        assert valid_label in result["valid"]
        assert "新标签ABC" in result["candidates"]

    def test_narrative_validation(self):
        nt = load_taxonomy("narrative_categories")
        valid_label = nt.flat_labels()[0]
        result = validate_tags([valid_label], nt)
        assert valid_label in result["valid"]
        assert len(result["candidates"]) == 0

    def test_case_insensitive(self):
        rt = load_taxonomy("risk_tags")
        valid = rt.flat_labels()
        if valid:
            upper = valid[0].upper()
            result = validate_tags([upper], rt)
            # Should match case-insensitively (all stored lowercase)
            assert len(result["valid"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tag limiting
# ═══════════════════════════════════════════════════════════════════════════════

class TestLimitTags:
    """Verify tag count enforcement."""

    def test_under_limit(self):
        result = limit_tags(["a", "b"], max_n=3)
        assert result == ["a", "b"]

    def test_at_limit(self):
        result = limit_tags(["a", "b", "c"], max_n=3)
        assert result == ["a", "b", "c"]

    def test_over_limit(self):
        result = limit_tags(["a", "b", "c", "d"], max_n=3)
        assert result == ["a", "b", "c"]


# ═══════════════════════════════════════════════════════════════════════════════
# Candidate tag management
# ═══════════════════════════════════════════════════════════════════════════════

class TestCandidateManagement:
    """Verify candidate tag lifecycle."""

    def test_suggest_candidates_persists(self):
        """suggest_candidates should write to candidate_tags.json."""
        # Clear first
        _save_candidates({"pending": [], "approved": [], "rejected": []})
        suggest_candidates(["测试候选标签"], "risk_tag")
        data = _load_candidates()
        labels = [e["label"] for e in data.get("pending", [])]
        assert "测试候选标签" in labels

    def test_approve_moves_to_approved(self):
        _save_candidates({"pending": [
            {"label": "待审批标签", "category": "risk_tag"}
        ], "approved": [], "rejected": []})
        result = approve_candidate("待审批标签")
        assert result is True
        data = _load_candidates()
        pending_labels = [e["label"] for e in data.get("pending", [])]
        approved_labels = [e["label"] for e in data.get("approved", [])]
        assert "待审批标签" not in pending_labels
        assert "待审批标签" in approved_labels

    def test_reject_moves_to_rejected(self):
        _save_candidates({"pending": [
            {"label": "要拒绝的标签", "category": "risk_tag"}
        ], "approved": [], "rejected": []})
        result = reject_candidate("要拒绝的标签")
        assert result is True
        data = _load_candidates()
        pending_labels = [e["label"] for e in data.get("pending", [])]
        rejected_labels = [e["label"] for e in data.get("rejected", [])]
        assert "要拒绝的标签" not in pending_labels
        assert "要拒绝的标签" in rejected_labels

    def test_approve_nonexistent_returns_false(self):
        _save_candidates({"pending": [], "approved": [], "rejected": []})
        result = approve_candidate("不存在的标签")
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt section building
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromptSection:
    """Verify prompt section generation for LLM context."""

    def test_build_prompt_section(self):
        nt = load_taxonomy("narrative_categories")
        rt = load_taxonomy("risk_tags")
        section = build_taxonomy_prompt_section(nt, rt)
        assert "受控词表" in section
        assert "叙事分类" in section
        assert "风险标签" in section

    def test_prompt_contains_labels(self):
        nt = load_taxonomy("narrative_categories")
        rt = load_taxonomy("risk_tags")
        section = build_taxonomy_prompt_section(nt, rt)
        # Should contain at least one L1 name
        l1_names = [n.name for n in nt.nodes]
        found = any(name in section for name in l1_names)
        assert found, f"Expected at least one L1 name in prompt, got none from {l1_names}"


# ═══════════════════════════════════════════════════════════════════════════════
# Serialization round-trip
# ═══════════════════════════════════════════════════════════════════════════════

class TestSerialization:
    """Verify taxonomy node serialization round-trips correctly."""

    def test_round_trip_hierarchical(self):
        nodes = [
            TaxonomyNode(name="测试L1", description="测试描述", children=[
                TaxonomyNode(name="测试L2", keywords=["k1", "k2"], parent="测试L1"),
            ]),
        ]
        text = _serialize_taxonomy_nodes(nodes, is_flat=False)
        assert "## 测试L1" in text
        assert "测试L2" in text
        assert "k1, k2" in text
        # Parse back
        parsed = _parse_taxonomy_body(text, is_flat=False)
        assert len(parsed) == 1
        assert parsed[0].name == "测试L1"
        assert parsed[0].children[0].name == "测试L2"
        assert parsed[0].children[0].keywords == ["k1", "k2"]

    def test_round_trip_flat(self):
        nodes = [
            TaxonomyNode(name="测试大类", children=[
                TaxonomyNode(name="测试标签", description="标签描述", parent="测试大类"),
            ]),
        ]
        text = _serialize_taxonomy_nodes(nodes, is_flat=True)
        assert "## 测试大类" in text
        parsed = _parse_taxonomy_body(text, is_flat=True)
        assert len(parsed) == 1
        assert parsed[0].children[0].name == "测试标签"
        assert parsed[0].children[0].description == "标签描述"


# ═══════════════════════════════════════════════════════════════════════════════
# Taxonomy CRUD (add_l2_node / remove_l2_node / add_l1_node)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_taxonomy_file(tmp_path):
    """Create a temporary taxonomy .md file for CRUD testing."""
    content = """---
title: Test Taxonomy
type: taxonomy
taxonomy_type: narrative_category
version: 1
---

# Test Taxonomy

## 产品质量
- **定义**: 产品相关
- **子类**:
  - 食品安全 (异物, 添加剂)

## 企业行为
- **定义**: 企业相关
- **子类**:
  - 劳工争议 (裁员, 欠薪)
"""
    tax_dir = tmp_path / "taxonomy"
    tax_dir.mkdir()
    fpath = tax_dir / "test_tax.md"
    fpath.write_text(content, encoding="utf-8")
    return fpath


class TestTaxonomyCRUD:
    """Verify add/remove operations on taxonomy nodes."""

    def test_serialize_empty(self):
        text = _serialize_taxonomy_nodes([], is_flat=False)
        assert text == ""

    def test_add_l2_appends(self, monkeypatch, tmp_path, temp_taxonomy_file):
        from engine import taxonomy_mgr
        # Patch paths to use temp directory
        monkeypatch.setattr(taxonomy_mgr, "TAXONOMY_DIR", tmp_path / "taxonomy")
        monkeypatch.setattr(taxonomy_mgr, "CANDIDATE_PATH", tmp_path / "taxonomy" / "candidate_tags.json")
        _reload_cache("test_tax")

        ok = add_l2_node("test_tax", "产品质量", "新增子类", keywords=["kw1"])
        assert ok is True

        tax = load_taxonomy("test_tax")
        l2_names = [c.name for c in tax.nodes[0].children]
        assert "新增子类" in l2_names

    def test_remove_l2_deletes(self, monkeypatch, tmp_path, temp_taxonomy_file):
        from engine import taxonomy_mgr
        monkeypatch.setattr(taxonomy_mgr, "TAXONOMY_DIR", tmp_path / "taxonomy")
        monkeypatch.setattr(taxonomy_mgr, "CANDIDATE_PATH", tmp_path / "taxonomy" / "candidate_tags.json")
        _reload_cache("test_tax")

        ok = remove_l2_node("test_tax", "产品质量", "食品安全")
        assert ok is True

        tax = load_taxonomy("test_tax")
        l2_names = [c.name for c in tax.nodes[0].children]
        assert "食品安全" not in l2_names

    def test_add_duplicate_returns_false(self, monkeypatch, tmp_path, temp_taxonomy_file):
        from engine import taxonomy_mgr
        monkeypatch.setattr(taxonomy_mgr, "TAXONOMY_DIR", tmp_path / "taxonomy")
        monkeypatch.setattr(taxonomy_mgr, "CANDIDATE_PATH", tmp_path / "taxonomy" / "candidate_tags.json")
        _reload_cache("test_tax")

        ok = add_l2_node("test_tax", "产品质量", "食品安全")
        assert ok is False  # already exists

    def test_add_l1_creates_category(self, monkeypatch, tmp_path, temp_taxonomy_file):
        from engine import taxonomy_mgr
        monkeypatch.setattr(taxonomy_mgr, "TAXONOMY_DIR", tmp_path / "taxonomy")
        monkeypatch.setattr(taxonomy_mgr, "CANDIDATE_PATH", tmp_path / "taxonomy" / "candidate_tags.json")
        _reload_cache("test_tax")

        ok = add_l1_node("test_tax", "新大类", description="新测试大类")
        assert ok is True

        tax = load_taxonomy("test_tax")
        l1_names = [n.name for n in tax.nodes]
        assert "新大类" in l1_names
        assert tax.nodes[-1].description == "新测试大类"

    def test_add_l1_duplicate_returns_false(self, monkeypatch, tmp_path, temp_taxonomy_file):
        from engine import taxonomy_mgr
        monkeypatch.setattr(taxonomy_mgr, "TAXONOMY_DIR", tmp_path / "taxonomy")
        monkeypatch.setattr(taxonomy_mgr, "CANDIDATE_PATH", tmp_path / "taxonomy" / "candidate_tags.json")
        _reload_cache("test_tax")

        ok = add_l1_node("test_tax", "产品质量")
        assert ok is False

    def test_remove_nonexistent_l2_returns_false(self, monkeypatch, tmp_path, temp_taxonomy_file):
        from engine import taxonomy_mgr
        monkeypatch.setattr(taxonomy_mgr, "TAXONOMY_DIR", tmp_path / "taxonomy")
        monkeypatch.setattr(taxonomy_mgr, "CANDIDATE_PATH", tmp_path / "taxonomy" / "candidate_tags.json")
        _reload_cache("test_tax")

        ok = remove_l2_node("test_tax", "企业行为", "不存在的子类")
        assert ok is False
