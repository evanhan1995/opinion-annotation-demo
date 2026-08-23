# -*- coding: utf-8 -*-
"""P0/P1 双 Agent 复核测试 —— review_severity / 三档措辞 / orchestrator 集成 / 落盘 / 回归。"""

import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import agents.reviewer as reviewer_mod
import agents.shared as sh
from agents.shared import RawData, Annotation, SeverityReviewResult


def _make_annotation(severity="P1"):
    return Annotation(
        url="https://x.com/1", platform="weibo", severity=severity,
        severity_reason="r", sentiment="负面", risk_tags=[], triage="上升PR",
        comment_risk="黄", summary="s",
    )


def _make_raw(content="这是一条测试内容"):
    return RawData(url="https://x.com/1", platform="weibo", title="t", content=content)


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_severity：JSON 键精准提取，理由里的 severity 提及不应干扰
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractSeverity:
    def test_json_key_extracts_judgment_not_reason(self):
        # 判定 P1，理由里提到 P0 → 应提取 P1（第一层精准匹配 JSON 键）
        text = '{"严重度": "P1", "理由": "这不属于P0级别的事故，属一般负面舆情"}'
        assert reviewer_mod._extract_severity(text) == "P1"

    def test_json_reason_mentions_higher_severity(self):
        # 判定 P2，理由里提到 P0 → 仍应提取 P2
        text = '{"严重度": "P2", "理由": "虽提及死亡但非本次主因，不构成P0"}'
        assert reviewer_mod._extract_severity(text) == "P2"

    def test_bare_fallback_first_occurrence(self):
        # 无 JSON 键时 fallback 取第一个裸 P0-P3（判定在前 → 正确）
        assert reviewer_mod._extract_severity("严重度：P1，理由：这不属于P0") == "P1"

    def test_extract_empty(self):
        assert reviewer_mod._extract_severity("没有任何严重度提及") == ""


# ═══════════════════════════════════════════════════════════════════════════════
# review_severity 单元测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewSeverity:
    def test_consistent(self, monkeypatch):
        monkeypatch.setattr(reviewer_mod, "_call_reviewer_llm", lambda raw: ("P1", "一致理由"))
        ann = _make_annotation("P1")
        result = reviewer_mod.review_severity(_make_raw(), ann)
        assert result.review_severity == "P1"
        assert result.is_consistent is True

    def test_divergent(self, monkeypatch):
        monkeypatch.setattr(reviewer_mod, "_call_reviewer_llm", lambda raw: ("P2", "分歧理由"))
        ann = _make_annotation("P1")
        result = reviewer_mod.review_severity(_make_raw(), ann)
        assert result.review_severity == "P2"
        assert result.is_consistent is False

    def test_sentinel_reference_hits(self):
        assert reviewer_mod._sentinel_severity_reference("用户集体投诉产品质量问题") == "P1"

    def test_sentinel_reference_none(self):
        assert reviewer_mod._sentinel_severity_reference("今天天气不错") == "无命中"

    def test_llm_failure_fallback(self, monkeypatch):
        monkeypatch.setattr(reviewer_mod, "_call_reviewer_llm", lambda raw: ("", "复核不可用: boom"))
        ann = _make_annotation("P1")
        result = reviewer_mod.review_severity(_make_raw(), ann)
        assert result.review_severity == ""
        assert result.is_consistent is False
        assert "复核不可用" in result.review_reason


# ═══════════════════════════════════════════════════════════════════════════════
# review_dispute_text 三档措辞
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewDisputeText:
    def test_not_disputed_returns_empty(self):
        assert reviewer_mod.review_dispute_text(_make_annotation("P1")) == ""

    def test_sentinel_backs_initial(self):
        ann = _make_annotation("P1")
        ann.review_disputed = True
        ann.review_severity = "P2"
        ann.sentinel_reference = "P1"
        assert "复核可能低估" in reviewer_mod.review_dispute_text(ann)

    def test_obvious_downgrade_gap2(self):
        ann = _make_annotation("P0")
        ann.review_disputed = True
        ann.review_severity = "P2"
        ann.sentinel_reference = "无命中"
        assert "初判可能高估" in reviewer_mod.review_dispute_text(ann)

    def test_mild_downgrade_gap1_neutral(self):
        ann = _make_annotation("P1")
        ann.review_disputed = True
        ann.review_severity = "P2"
        ann.sentinel_reference = "无命中"
        assert "规则引擎未提供额外信号" in reviewer_mod.review_dispute_text(ann)

    def test_review_failed(self):
        ann = _make_annotation("P1")
        ann.review_disputed = False
        ann.review_severity = ""
        ann.review_reason = "复核不可用: x"
        assert "复核不可用" in reviewer_mod.review_dispute_text(ann)


# ═══════════════════════════════════════════════════════════════════════════════
# annotation_to_engine_dict 落盘字段流转
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnnotationToEngineDict:
    def test_review_fields_flow(self):
        ann = _make_annotation("P1")
        ann.review_severity = "P2"
        ann.review_disputed = True
        ann.sentinel_reference = "无命中"
        d = sh.annotation_to_engine_dict(ann)
        assert d["review_severity"] == "P2"
        assert d["review_disputed"] is True
        assert d["sentinel_reference"] == "无命中"

    def test_no_review_fields_when_empty(self):
        d = sh.annotation_to_engine_dict(_make_annotation("P2"))
        assert "review_severity" not in d
        assert "review_disputed" not in d
        assert "sentinel_reference" not in d


# ═══════════════════════════════════════════════════════════════════════════════
# _generate_auto_case 落盘 frontmatter
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateAutoCaseReviewFrontmatter:
    def _run(self, monkeypatch, tmp_path, annotation_result):
        import engine.ingestor as ingestor_mod
        cases = tmp_path / "cases"
        cases.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(ingestor_mod, "CASES_DIR", cases)
        # 隔离 INDEX_PATH：_check_boundaries 会读它，须避免依赖真实（可能被联网测试污染的）wiki/cases/index.md
        monkeypatch.setattr(ingestor_mod, "INDEX_PATH", cases / "index.md")
        scraped_data = {
            "原文内容": "测试", "来源平台": "微博", "发布者类型": "t",
            "互动数据": "", "发布时间": "2026-08-23", "原文链接": "https://x.com/1",
        }
        filename = ingestor_mod._generate_auto_case(
            scraped_data, annotation_result, url="https://x.com/1",
            init_status="待跟进", case_id="case-999",
        )
        files = list(cases.rglob("case-*.md"))
        assert len(files) == 1, files
        return files[0].read_text(encoding="utf-8")

    def test_review_fields_written(self, monkeypatch, tmp_path):
        annotation_result = {
            "严重度评级": "P1", "分流建议": "上升PR", "摘要": "测试摘要",
            "严重度理由": "理由", "情感分析": {"整体情感": "负面"},
            "风险标签": [], "舆情分类": [],
            "review_severity": "P2", "review_disputed": True, "sentinel_reference": "无命中",
        }
        content = self._run(monkeypatch, tmp_path, annotation_result)
        assert "review_severity: P2" in content
        assert "review_disputed: true" in content
        assert "sentinel_reference: 无命中" in content

    def test_p3_no_review_fields(self, monkeypatch, tmp_path):
        annotation_result = {
            "严重度评级": "P3", "分流建议": "内部研判", "摘要": "测试摘要",
            "严重度理由": "理由", "情感分析": {"整体情感": "中性"},
            "风险标签": [], "舆情分类": [],
        }
        content = self._run(monkeypatch, tmp_path, annotation_result)
        assert "review_severity:" not in content
        assert "review_disputed:" not in content


# ═══════════════════════════════════════════════════════════════════════════════
# orchestrator 集成测试（mock 全 pipeline，只验证复核插入点）
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorReview:
    def _run(self, monkeypatch, severity, review_sev, review_reason, sentinel_ref):
        import agents.orchestrator as orch
        import agents.scraper as scraper_mod
        import agents.analyst as analyst_mod
        import agents.sentinel as sentinel_mod
        import agents.curator as curator_mod
        from agents.shared import ActionPlan, KBEntry

        raw = RawData(url="https://x.com/1", platform="weibo", title="t", content="c")
        ann = _make_annotation(severity)
        review = SeverityReviewResult(
            initial_severity=severity, review_severity=review_sev,
            sentinel_reference=sentinel_ref,
            is_consistent=(review_sev == severity),
            review_reason=review_reason,
        )

        monkeypatch.setattr(scraper_mod, "fetch", lambda url: raw)
        monkeypatch.setattr(scraper_mod, "detect_platform", lambda url: "weibo")
        monkeypatch.setattr(sentinel_mod, "screen_content", lambda c, p: None)
        monkeypatch.setattr(analyst_mod, "annotate", lambda raw, **kw: ann)

        review_calls = []
        def spy_review(raw_, a):
            review_calls.append(a.severity)
            return review
        monkeypatch.setattr(reviewer_mod, "review_severity", spy_review)

        ap = ActionPlan(case_id="case-001", status="待跟进", steps=[], escalated_departments=[], deadline="")
        monkeypatch.setattr("agents.handler.triage", lambda a, cid: ap)
        ke = KBEntry(case_id="case-001", url=raw.url, platform=raw.platform,
                     severity=severity, status="待跟进", ingested_at="", title="t")
        monkeypatch.setattr(curator_mod, "ingest", lambda *a, **k: ke)

        emergency_calls = []
        def spy_emergency(annotation, notify_feishu=False):
            emergency_calls.append(annotation)
            return True
        monkeypatch.setattr(orch, "emergency_dispatch", spy_emergency)

        monkeypatch.setattr("engine.ingestor.get_next_case_id", lambda: "case-001")
        monkeypatch.setattr(orch, "record_scraper_success", lambda p: None)
        monkeypatch.setattr(orch, "record_scraper_failure", lambda p, r="": None)

        orch.run_passive_analysis("https://x.com/1")
        return ann, review_calls, emergency_calls

    def test_p1_consistent_alerts_no_dispute(self, monkeypatch):
        ann, review_calls, emergency_calls = self._run(monkeypatch, "P1", "P1", "一致", "无命中")
        assert review_calls == ["P1"]
        assert len(emergency_calls) == 1
        assert ann.review_disputed is False

    def test_p1_divergent_still_alerts_marks_dispute(self, monkeypatch):
        ann, review_calls, emergency_calls = self._run(monkeypatch, "P1", "P2", "分歧", "无命中")
        assert review_calls == ["P1"]
        assert len(emergency_calls) == 1  # 分歧仍告警
        assert ann.review_disputed is True

    def test_p2_no_review_no_emergency(self, monkeypatch):
        ann, review_calls, emergency_calls = self._run(monkeypatch, "P2", "", "", "")
        assert review_calls == []       # 未触发复核
        assert emergency_calls == []    # 未触发熔断
        assert ann.review_severity == ""

    def test_degraded_p3_no_review(self, monkeypatch):
        # degraded 案例 severity 恒为 P3（非 P0/P1）→ 不进复核分支（回归）
        ann, review_calls, emergency_calls = self._run(monkeypatch, "P3", "", "", "")
        assert review_calls == []
        assert emergency_calls == []
