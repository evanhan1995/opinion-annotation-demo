# -*- coding: utf-8 -*-
"""
舆情指挥系统 — Analyst Agent (分析员)

Responsibility (PRD §5.3):
  Annotate raw content: severity (P0-P3), sentiment, risk tags, triage,
  comment risk, category, + relevance check for Monitor-originated content.

Isolation constraints:
  - MUST NOT generate action plans (Handler's job)
  - MUST NOT modify KB (Curator's job)
  - MUST NOT directly call Monitor.record_feedback() (through Orchestrator)
  - System Prompt forbids: "不要建议具体处置步骤、不要修改知识库"

Model: DeepSeek (reasoning-heavy, strict JSON output).
"""
import io
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agents.shared import (
    load_prompt,
    RawData, Annotation, rawdata_to_engine_dict,
)


ANALYST_SYSTEM_PROMPT = ""  # Loaded lazily from prompts/analyst_system.txt


def _get_prompt() -> str:
    global ANALYST_SYSTEM_PROMPT
    if not ANALYST_SYSTEM_PROMPT:
        ANALYST_SYSTEM_PROMPT = load_prompt("analyst_system")
    return ANALYST_SYSTEM_PROMPT


def _engine_result_to_annotation(result: dict, url: str, platform: str,
                                  keyword_context: str = "") -> Annotation:
    """Convert engine/annotate.py result dict to Annotation dataclass."""
    comment_analysis = result.get("评论区分析", {}) or {}
    comment_risk = comment_analysis.get("评论红绿灯", {})
    risk_light = "绿"
    if isinstance(comment_risk, dict):
        red = comment_risk.get("红", 0)
        yellow = comment_risk.get("黄", 0)
        if red > 0:
            risk_light = "红"
        elif yellow > 0:
            risk_light = "黄"

    categories = result.get("舆情分类", [])
    if isinstance(categories, list):
        category_str = "|".join(categories)
    else:
        category_str = str(categories)

    return Annotation(
        url=url,
        platform=platform,
        severity=result.get("严重度", "P3"),
        severity_reason=result.get("严重度理由", ""),
        sentiment=result.get("情感", "中性"),
        risk_tags=result.get("风险标签", []),
        triage=result.get("分流建议", "内部研判"),
        comment_risk=risk_light,
        category=category_str,
        relevance="relevant",
        relevance_reason="",
        summary=result.get("摘要", "") or "",
    )


# ── Relevance check ────────────────────────────────────────────────────
def check_relevance(content: str, keyword: str, platform: str) -> tuple[bool, str]:
    """Relevance check for Monitor-originated content.

    Fast substring check only. Relevance is also assessed by the main
    annotation LLM via keyword_context in the user prompt — no secondary
    LLM call needed.
    """
    if not keyword:
        return True, ""

    kw_lower = keyword.lower()
    content_lower = content.lower()
    kw_parts = [p.strip() for p in kw_lower.split() if len(p.strip()) >= 2]
    if not kw_parts:
        return True, ""
    matched = sum(1 for p in kw_parts if p in content_lower)
    if matched >= len(kw_parts) * 0.5:
        return True, f"关键词 '{keyword}' 部分匹配内容"
    return False, f"关键词 '{keyword}' 未匹配内容（主标注LLM已含相关性判断）"


# ── Main annotation ────────────────────────────────────────────────────
def annotate(raw: RawData, keyword_context: str = "",
             similar_cases: list[dict] | None = None) -> Annotation:
    """Annotate raw content into structured assessment via DeepSeek."""
    from engine.annotate import build_system_prompt, format_user_message, annotate_one, load_config

    engine_input = rawdata_to_engine_dict(raw)
    config = load_config()
    system_prompt, _stats = build_system_prompt(raw.content)
    user_msg = format_user_message(engine_input)

    if keyword_context:
        user_msg += (
            f"\n\n**关联关键词**：{keyword_context}\n"
            "请同时判断此内容是否与关键词相关。如果无关，在\"分流建议\"中给出\"忽略\"。"
        )

    result = annotate_one(user_msg, system_prompt, config)

    if result.get("error"):
        # Fallback: return mock-like annotation with error info
        return Annotation(
            url=raw.url, platform=raw.platform,
            severity="P2", severity_reason=f"[LLM error: {result.get('message', 'unknown')}]",
            sentiment="中性", risk_tags=[], triage="内部研判", comment_risk="绿",
            summary=f"[Error] {raw.title[:80]}" if raw.title else "[Error]",
        )

    annotation = _engine_result_to_annotation(result, raw.url, raw.platform, keyword_context)

    if keyword_context:
        is_rel, rel_reason = check_relevance(raw.content, keyword_context, raw.platform)
        if not is_rel and annotation.triage == "忽略":
            annotation.relevance = f"irrelevant_{keyword_context}_{raw.platform}"
            annotation.relevance_reason = rel_reason

    return annotation


def annotate_stream(raw: RawData, keyword_context: str = ""):
    """Streaming annotation — yields chunks then final result."""
    from engine.annotate import build_system_prompt, format_user_message, annotate_one_stream, load_config

    engine_input = rawdata_to_engine_dict(raw)
    config = load_config()
    system_prompt, _stats = build_system_prompt(raw.content)
    user_msg = format_user_message(engine_input)

    if keyword_context:
        user_msg += f"\n\n**关联关键词**：{keyword_context}"

    for event in annotate_one_stream(user_msg, system_prompt, config):
        if event.get("type") == "result":
            data = event["data"]
            if data.get("error"):
                yield {"type": "error", "message": data.get("message", "unknown")}
            else:
                annotation = _engine_result_to_annotation(data, raw.url, raw.platform, keyword_context)
                yield {"type": "result", "annotation": annotation}
        else:
            yield event
