# -*- coding: utf-8 -*-
"""Handler Agent interface tests — Phase 1 skeleton validation."""
import io
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pytest
from agents.shared import Annotation
from agents.handler import (
    triage, validate_transition, transition_status,
    ActionPlan, VALID_TRANSITIONS,
)


SAMPLE_ANNOTATION = Annotation(
    url="https://example.com", platform="douyin",
    severity="P1", severity_reason="test", sentiment="负面",
    risk_tags=["产品质量"], triage="上升PR", comment_risk="黄",
    summary="test summary",
)


class TestStateMachine:
    def test_valid_transitions(self):
        assert validate_transition("待跟进", "处理中") is True
        assert validate_transition("待跟进", "已处理") is True
        assert validate_transition("待跟进", "已放弃") is True
        assert validate_transition("待跟进", "忽略") is True
        assert validate_transition("处理中", "已处理") is True
        assert validate_transition("处理中", "已放弃") is True

    def test_invalid_transitions(self):
        assert validate_transition("已处理", "处理中") is False
        assert validate_transition("忽略", "处理中") is False
        assert validate_transition("处理中", "待跟进") is False

    def test_terminal_states_no_exit(self):
        for state in ["已处理", "已放弃", "忽略"]:
            assert VALID_TRANSITIONS.get(state, []) == []

    def test_all_five_states_exist(self):
        assert set(VALID_TRANSITIONS.keys()) == {"待跟进", "处理中", "已处理", "已放弃", "忽略"}


class TestTransitionFunction:
    def test_successful_transition(self):
        result = transition_status("case-001", "待跟进", "处理中", "开始处理")
        assert result["success"] is True
        assert result["to_status"] == "处理中"

    def test_failed_transition(self):
        result = transition_status("case-001", "已处理", "处理中")
        assert result["success"] is False
        assert "error" in result


class TestTriage:
    def test_returns_action_plan(self):
        plan = triage(SAMPLE_ANNOTATION)
        assert isinstance(plan, ActionPlan)
        assert plan.case_id
        assert plan.status == "待跟进"

    def test_p0_gets_escalation(self):
        p0 = Annotation(url="x", platform="x", severity="P0", severity_reason="x",
                        sentiment="负面", risk_tags=["x"], triage="上升PR", comment_risk="红", summary="x")
        plan = triage(p0)
        assert len(plan.escalated_departments) > 0

    def test_plan_has_steps(self):
        plan = triage(SAMPLE_ANNOTATION)
        assert len(plan.steps) > 0

    def test_plan_has_deadline(self):
        plan = triage(SAMPLE_ANNOTATION)
        assert plan.deadline
