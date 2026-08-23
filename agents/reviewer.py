# -*- coding: utf-8 -*-
"""Reviewer Agent -- 对 P0/P1 初判做独立严重度复核。

Responsibility (PRD: P0/P1 双 Agent 复核):
  对 Analyst 判为 P0/P1 的案例，用第二个 LLM（同模型、独立 prompt）+ Sentinel
  规则参考，从零开始独立判断严重度。只读、不改标注、不改 KB。

Isolation constraints:
  - MUST NOT modify KB (Curator's job)
  - MUST NOT change the original annotation severity (Analyst's job)
  - Read-only：只返回复核意见，分歧时由 Orchestrator 决定告警措辞
  - All LLM calls via shared.get_llm("deepseek")（对齐 forum.py）
"""

import re

from agents.shared import (
    get_llm, load_prompt, RawData, Annotation, SeverityReviewResult,
)

_REVIEWER_SYSTEM_PROMPT = ""

_SEVERITY_LEVELS = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _get_reviewer_prompt() -> str:
    global _REVIEWER_SYSTEM_PROMPT
    if not _REVIEWER_SYSTEM_PROMPT:
        _REVIEWER_SYSTEM_PROMPT = load_prompt("reviewer_system")
    return _REVIEWER_SYSTEM_PROMPT


def _sentinel_severity_reference(content: str) -> str:
    """Sentinel 规则引擎的严重度参考（免费、确定性，不调 LLM）。"""
    try:
        from agents.sentinel import apply_rules
        result = apply_rules(content)
        sev = result.suggested_severity
        return sev if sev in ("P0", "P1", "P2", "P3") else "无命中"
    except Exception:
        return "无命中"


def _extract_severity(text: str) -> str:
    """从复核输出里提取 P0-P3（容忍 JSON 或纯文本）。"""
    if not text:
        return ""
    m = re.search(r'"严重度"\s*:\s*"(P[0-3])"', text)
    if m:
        return m.group(1)
    m = re.search(r'\b(P[0-3])\b', text)
    if m:
        return m.group(1)
    return ""


def _call_reviewer_llm(raw: RawData) -> tuple[str, str]:
    """独立复核 LLM：DeepSeek + 独立 prompt + 低温度。返回 (severity, reason)。

    失败返回 ("", "复核不可用: ...")，不抛异常（复核失败不阻断告警）。
    """
    system_prompt = _get_reviewer_prompt()
    if not system_prompt:
        return "", "复核不可用: reviewer prompt 缺失"
    # 只喂原始内容，不喂初判 severity / 理由（独立性硬约束）
    text = raw.content or raw.title
    user_msg = f"平台：{raw.platform}\n\n内容：{text[:2000]}"
    try:
        client, model = get_llm("deepseek")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=200,
        )
        out = response.choices[0].message.content.strip()
        sev = _extract_severity(out)
        if not sev:
            return "", f"复核不可用: 未能解析 severity（输出: {out[:80]}）"
        return sev, out[:200]
    except Exception as e:
        return "", f"复核不可用: {e}"


def review_severity(raw: RawData, annotation: Annotation) -> SeverityReviewResult:
    """对 P0/P1 初判做独立复核（同模型不同 prompt + Sentinel 免费参考）。"""
    review_sev, review_reason = _call_reviewer_llm(raw)
    sentinel_ref = _sentinel_severity_reference(raw.content or raw.title)
    is_consistent = bool(review_sev) and (review_sev == annotation.severity)
    return SeverityReviewResult(
        initial_severity=annotation.severity,
        review_severity=review_sev,
        sentinel_reference=sentinel_ref,
        is_consistent=is_consistent,
        review_reason=review_reason,
    )


def review_dispute_text(annotation: Annotation) -> str:
    """返回 P0/P1「复核存疑」的告警措辞；非存疑（一致/未复核）返回 ""。

    三档措辞（分歧时）：
      1. Sentinel 命中 P0/P1（站初判）→ 复核可能低估
      2. Sentinel 无命中 + 复核低 ≥2 级（站复核·明显）→ 初判可能高估
      3. Sentinel 无命中 + 复核只低 1 级 → 中性
    复核 LLM 失败（review_severity 空但 review_reason 有值）→ 标记"复核不可用"。
    """
    if annotation.review_disputed:
        if annotation.sentinel_reference in ("P0", "P1"):
            return "复核可能低估，规则引擎仍命中高危词，建议人工优先确认"
        init_lv = _SEVERITY_LEVELS.get(annotation.severity, 99)
        review_lv = _SEVERITY_LEVELS.get(annotation.review_severity, 99)
        gap = review_lv - init_lv
        if gap >= 2:
            return "初判可能高估，规则引擎未命中高危词，疑为过度升级"
        return "复核结果与初判不同，规则引擎未提供额外信号，建议人工判断"
    # 复核失败（P0/P1 尝试复核但 LLM 失败）
    if not annotation.review_severity and annotation.review_reason:
        return "复核不可用，未完成二次判断"
    return ""
