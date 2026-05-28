# -*- coding: utf-8 -*-
"""
舆情指挥系统 — Handler Agent (处置跟进)

Responsibility (PRD §5.4):
  1. Generate action plans based on Analyst annotations
  2. Manage case status state machine (5 states)
  3. Sync status changes → Curator.update_case_status()

Isolation constraints:
  - MUST NOT re-analyze content or modify annotations (Analyst's domain)
  - MUST NOT write directly to wiki/cases/ (through Curator.update_case_status)
  - System Prompt forbids: "不要重新分析内容、不要修改标注结果"

Model: DeepSeek (logical consistency, structured output).
"""
import io
import sys
from dataclasses import dataclass
from datetime import datetime

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agents.shared import Annotation, ActionPlan


# ── Status state machine ───────────────────────────────────────────────
VALID_TRANSITIONS = {
    "待跟进": ["处理中", "已处理", "已放弃", "忽略"],
    "处理中": ["已处理", "已放弃"],
    "已处理": [],    # terminal
    "已放弃": [],    # terminal
    "忽略": [],      # terminal
}


def validate_transition(from_status: str, to_status: str) -> bool:
    """Check if a status transition is valid."""
    allowed = VALID_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def transition_status(case_id: str, from_status: str, to_status: str, notes: str = "") -> dict:
    """Attempt a status transition. Returns result dict.

    Curator.update_case_status() is called by Orchestrator after this.
    """
    if not validate_transition(from_status, to_status):
        return {
            "success": False,
            "error": f"Invalid transition: {from_status} → {to_status}. Allowed: {VALID_TRANSITIONS.get(from_status, [])}"
        }
    return {
        "success": True,
        "case_id": case_id,
        "from_status": from_status,
        "to_status": to_status,
        "timestamp": datetime.now().isoformat(),
        "notes": notes,
    }


# ── Action plan generation ─────────────────────────────────────────────
def triage(annotation: Annotation) -> ActionPlan:
    """Generate action plan from annotation via rule engine.

    Severity + triage recommendation → deterministic steps + escalation.
    Replaces the previous DeepSeek LLM call (saves ~300 tokens per item).
    """
    case_id = f"case-{datetime.now().strftime('%Y%m%d%H%M')}"
    sev = annotation.severity
    triage_type = annotation.triage

    # ── Rule matrix ──────────────────────────────────────────────────
    if sev == "P0":
        status = "待跟进"
        steps = ["核实原始内容真实性", "评估是否需要上升到管理层", "启动24小时应急响应"]
        escalated = ["PR部", "法务部"]
        notes = "P0高优案例，需紧急处置"
    elif sev == "P1":
        status = "待跟进"
        steps = ["核实原始内容真实性", "评估是否需要上升"]
        escalated = ["PR部"]
        notes = "P1高优案例"
    elif triage_type in ("上升法务", "上升PR"):
        status = "待跟进"
        steps = ["核实原始内容真实性", "记录至舆情台账", "定期跟踪监测"]
        escalated = ["法务部"] if triage_type == "上升法务" else ["PR部"]
        notes = f"分流建议: {triage_type}"
    else:
        status = "待跟进"
        steps = ["记录至舆情台账", "定期跟踪监测"]
        escalated = []
        notes = ""

    return ActionPlan(
        case_id=case_id,
        status=status,
        steps=steps,
        escalated_departments=escalated,
        deadline=datetime.now().strftime("%Y-%m-%d"),
        notes=notes,
    )
