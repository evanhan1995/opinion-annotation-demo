# -*- coding: utf-8 -*-
"""纠偏链路增强测试 —— 字段覆盖 / list 顺序不敏感 / correction json 落盘 / _meta 对称清洗。"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import engine.correction_handler as correction_handler
import engine.ingestor as ingestor
from engine.annotate import diff_annotations
from engine.constants import ANNOTATION_COMPARABLE_FIELDS, extract_annotation_diffs
from engine.correction_handler import (
    _save_correction_json,
    compare_and_decide,
    handle_correction,
)


# ═══════════════════════════════════════════════════════════════════════════════
# compare_and_decide：扩展字段覆盖（此前遗漏的字段应判 minor 而非 none）
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompareAndDecideExtended:
    @staticmethod
    def _ai(**overrides):
        base = {
            "严重度评级": "P2",
            "分流建议": "持续观察",
            "情感分析": {"整体情感": "中性"},
            "叙事分类": "行业生态/技术变革",
            "真实性评估": "无法核实",
            "风险标签": ["产品质量"],
            "舆情分类": [],
            "评论区分析": {"评论红绿灯": {"红": 0, "黄": 0, "绿": 0}, "评论总结": "无评论"},
            "摘要": "原摘要",
            "严重度理由": "原理由",
        }
        base.update(overrides)
        return base

    def test_risk_tags_change_is_detected(self):
        level, diffs = compare_and_decide(self._ai(风险标签=["产品质量"]), self._ai(风险标签=["产品质量", "安全"]))
        assert level == "minor"
        assert "风险标签" in diffs

    def test_summary_change_is_detected(self):
        level, diffs = compare_and_decide(self._ai(摘要="原摘要"), self._ai(摘要="新摘要"))
        assert level == "minor"
        assert "摘要" in diffs

    def test_narrative_category_change_is_detected(self):
        level, diffs = compare_and_decide(self._ai(叙事分类="行业生态"), self._ai(叙事分类="产品问题"))
        assert level == "minor"
        assert "叙事分类" in diffs

    def test_authenticity_change_is_detected(self):
        level, diffs = compare_and_decide(self._ai(真实性评估="无法核实"), self._ai(真实性评估="属实"))
        assert level == "minor"
        assert "真实性评估" in diffs

    def test_category_list_change_is_detected(self):
        level, diffs = compare_and_decide(self._ai(舆情分类=["产品质量"]), self._ai(舆情分类=["产品质量", "售后"]))
        assert level == "minor"
        assert "舆情分类" in diffs

    def test_comment_summary_change_is_detected(self):
        human = self._ai()
        human["评论区分析"]["评论总结"] = "风向负面"
        level, diffs = compare_and_decide(self._ai(), human)
        assert level == "minor"
        assert "评论区分析.评论总结" in diffs

    def test_severity_reason_change_is_detected(self):
        level, diffs = compare_and_decide(self._ai(严重度理由="原理由"), self._ai(严重度理由="新理由"))
        assert level == "minor"
        assert "严重度理由" in diffs

    def test_list_order_insensitive(self):
        ai = self._ai(风险标签=["a", "b"], 舆情分类=["x", "y"])
        human = self._ai(风险标签=["b", "a"], 舆情分类=["y", "x"])
        level, diffs = compare_and_decide(ai, human)
        assert level == "none"
        assert diffs == {}


# ═══════════════════════════════════════════════════════════════════════════════
# extract_annotation_diffs：扁平差异提取
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractAnnotationDiffs:
    def test_flat_structure(self):
        diffs = extract_annotation_diffs(
            {"严重度评级": "P2", "风险标签": ["a"]},
            {"严重度评级": "P1", "风险标签": ["a", "b"]},
        )
        assert all(set(d.keys()) == {"field", "old_value", "new_value"} for d in diffs)
        fields = {d["field"] for d in diffs}
        assert "严重度评级" in fields
        assert "风险标签" in fields

    def test_list_symmetric_difference(self):
        # 顺序不同 → 无变化
        assert extract_annotation_diffs({"风险标签": ["a", "b"]}, {"风险标签": ["b", "a"]}) == []
        # 增删 → 有变化
        assert len(extract_annotation_diffs({"风险标签": ["a"]}, {"风险标签": ["a", "b"]})) == 1

    def test_nested_path(self):
        diffs = extract_annotation_diffs(
            {"情感分析": {"整体情感": "中性"}},
            {"情感分析": {"整体情感": "负面"}},
        )
        assert len(diffs) == 1
        assert diffs[0]["field"] == "情感分析.整体情感"
        assert diffs[0]["old_value"] == "中性"
        assert diffs[0]["new_value"] == "负面"


# ═══════════════════════════════════════════════════════════════════════════════
# diff_annotations：字段范围扩大 + 返回结构不变 + list 对称差
# ═══════════════════════════════════════════════════════════════════════════════

class TestDiffAnnotations:
    def test_return_structure_unchanged(self):
        diffs = diff_annotations(
            {"严重度评级": "P2", "分流建议": "持续观察"},
            {"严重度评级": "P1", "分流建议": "持续观察"},
        )
        assert isinstance(diffs, list)
        assert len(diffs) == 1
        d = diffs[0]
        assert set(d.keys()) == {"field", "label", "old_value", "new_value"}
        assert d["field"] == "严重度评级"
        assert d["label"] == "严重度"
        assert d["old_value"] == "P2"
        assert d["new_value"] == "P1"

    def test_list_order_insensitive(self):
        assert diff_annotations({"风险标签": ["a", "b"]}, {"风险标签": ["b", "a"]}) == []

    def test_detects_narrative_category(self):
        diffs = diff_annotations({"叙事分类": "行业生态"}, {"叙事分类": "产品问题"})
        assert len(diffs) == 1
        assert diffs[0]["field"] == "叙事分类"

    def test_traffic_light_formatted(self):
        diffs = diff_annotations(
            {"评论区分析": {"评论红绿灯": {"红": 0, "黄": 0, "绿": 0}}},
            {"评论区分析": {"评论红绿灯": {"红": 1, "黄": 0, "绿": 0}}},
        )
        assert len(diffs) == 1
        assert diffs[0]["field"] == "评论区分析.评论红绿灯"
        assert diffs[0]["old_value"] == "红0/黄0/绿0"
        assert diffs[0]["new_value"] == "红1/黄0/绿0"


# ═══════════════════════════════════════════════════════════════════════════════
# _save_correction_json：significant / minor 两种落盘
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaveCorrectionJson:
    def test_minor_flat_diffs_and_null_case(self, tmp_path, monkeypatch):
        monkeypatch.setattr(correction_handler, "OUTPUT_DIR", tmp_path)
        filename = _save_correction_json(
            url="https://www.weibo.com/123456",
            platform="微博",
            diff_level="minor",
            ai_output={"严重度评级": "P2", "风险标签": []},
            human_correction={"严重度评级": "P2", "风险标签": ["安全"]},
            diffs={"风险标签": {"ai": [], "human": ["安全"]}},
            case_file=None,
        )
        assert filename and filename.endswith("_correction.json")
        payload = json.loads((tmp_path / filename).read_text(encoding="utf-8"))
        assert payload["source"] == "human_correction"
        assert payload["diff_level"] == "minor"
        assert payload["case_file"] is None
        assert payload["diffs"] == [{"field": "风险标签", "old_value": [], "new_value": ["安全"]}]

    def test_significant_sets_case_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(correction_handler, "OUTPUT_DIR", tmp_path)
        filename = _save_correction_json(
            url="https://www.weibo.com/123456",
            platform="微博",
            diff_level="significant",
            ai_output={"严重度评级": "P2"},
            human_correction={"严重度评级": "P1"},
            diffs={"严重度评级": {"ai": "P2", "human": "P1"}},
            case_file="case-340.md",
        )
        payload = json.loads((tmp_path / filename).read_text(encoding="utf-8"))
        assert payload["diff_level"] == "significant"
        assert payload["case_file"] == "case-340.md"
        assert payload["diffs"] == [{"field": "严重度评级", "old_value": "P2", "new_value": "P1"}]


# ═══════════════════════════════════════════════════════════════════════════════
# handle_correction：入口统一清洗 _meta（case 与 correction json 两侧对称）
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetaSymmetricCleaning:
    @staticmethod
    def _setup(tmp_path, monkeypatch):
        cases = tmp_path / "cases"
        cases.mkdir(parents=True, exist_ok=True)
        outputs = tmp_path / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(ingestor, "CASES_DIR", cases)
        monkeypatch.setattr(ingestor, "_case_id_reserved", None)
        monkeypatch.setattr(correction_handler, "OUTPUT_DIR", outputs)
        monkeypatch.setattr(correction_handler, "LOG_PATH", tmp_path / "log.md")
        # 隔离 index_mgr 写入，避免污染真实 wiki/cases/index.md
        monkeypatch.setattr(correction_handler, "update_case_index", lambda *a, **k: None)
        return cases, outputs

    def test_significant_cleans_meta_both_sides(self, tmp_path, monkeypatch):
        cases, outputs = self._setup(tmp_path, monkeypatch)
        ai_output = {
            "严重度评级": "P2",
            "分流建议": "持续观察",
            "情感分析": {"整体情感": "中性"},
            "摘要": "测试摘要",
            "_meta": {"model": "deepseek-chat"},
        }
        human_correction = {
            "严重度评级": "P1",
            "分流建议": "持续观察",
            "情感分析": {"整体情感": "中性"},
            "摘要": "测试摘要",
            "_meta": {"model": "deepseek-chat"},
        }
        original_input = {
            "原文内容": "测试内容",
            "来源平台": "微博",
            "原文链接": "https://www.weibo.com/123456",
            "发布者类型": "测试",
            "发布时间": "2026-08-22",
            "互动数据": "",
        }
        result = handle_correction(original_input, ai_output, human_correction, url="https://www.weibo.com/123456")

        assert result["action"] == "generated_case"
        # correction json 两侧无 _meta
        json_files = list(outputs.glob("*_correction.json"))
        assert len(json_files) == 1
        payload = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert "_meta" not in payload["ai_output"]
        assert "_meta" not in payload["human_correction"]
        # case-XXX.md 两侧无 _meta
        case_files = list(cases.rglob("case-*.md"))
        assert len(case_files) == 1
        case_content = case_files[0].read_text(encoding="utf-8")
        assert "_meta" not in case_content
        assert "## AI 原始标注" in case_content
        assert "## 人工修正标注" in case_content

    def test_minor_writes_json_and_log_not_case(self, tmp_path, monkeypatch):
        cases, outputs = self._setup(tmp_path, monkeypatch)
        ai_output = {"严重度评级": "P2", "分流建议": "持续观察", "摘要": "原摘要", "_meta": {"model": "x"}}
        human_correction = {"严重度评级": "P2", "分流建议": "持续观察", "摘要": "新摘要", "_meta": {"model": "x"}}
        original_input = {
            "原文内容": "c", "来源平台": "微博", "原文链接": "https://www.weibo.com/1",
            "发布者类型": "t", "发布时间": "2026-08-22", "互动数据": "",
        }
        result = handle_correction(original_input, ai_output, human_correction, url="https://www.weibo.com/1")

        assert result["action"] == "logged_only"
        assert result["case_file"] is None
        # 只生成 correction json，不生成 case
        assert len(list(outputs.glob("*_correction.json"))) == 1
        assert list(cases.rglob("case-*.md")) == []
        # 日志已写
        assert (tmp_path / "log.md").exists()
