# -*- coding: utf-8 -*-
"""Forum Agent -- cross-platform annotation cross-validation.

Responsibility (PRD v6.0):
  Detect cross-platform annotation contradictions using engine/linker.py
  cross-platform event matching, then use Host LLM to compare annotations
  and flag cases needing manual review.

Isolation constraints:
  - MUST NOT modify KB (Curator's job)
  - MUST NOT change annotation results (Analyst's job)
  - Read-only: reads linker results + annotation files, returns review flags
  - All LLM calls via shared.get_llm()
"""

import json
from pathlib import Path
from typing import Optional

import engine._compat
from agents.shared import (
    get_llm, load_prompt, PROJECT_ROOT, WIKI_DIR,
    ForumResult,
)

CASES_DIR = WIKI_DIR / "cases"
FORUM_HOST_PROMPT = ""


def _get_host_prompt() -> str:
    global FORUM_HOST_PROMPT
    if not FORUM_HOST_PROMPT:
        FORUM_HOST_PROMPT = load_prompt("forum_host")
    return FORUM_HOST_PROMPT


def _read_case_annotation(case_filename: str) -> Optional[dict]:
    """Read a case file and extract annotation fields."""
    case_path = CASES_DIR / case_filename
    if not case_path.exists():
        return None
    text = case_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    # Parse frontmatter
    fm = {}
    for line in parts[1].split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()

    body = parts[2]
    # Extract severity and sentiment from body (wiki annotation format)
    severity = ""
    sentiment = ""
    platform = fm.get("platform", "?")

    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("- **严重度**:"):
            severity = line.split("**:")[-1].strip() if "**:" in line else ""
        elif line.startswith("- **情感**:"):
            sentiment = line.split("**:")[-1].strip() if "**:" in line else ""

    return {
        "case_id": case_filename.replace(".md", ""),
        "platform": platform,
        "severity": severity,
        "sentiment": sentiment,
        "title": fm.get("title", ""),
        "tags": fm.get("tags", ""),
    }


def cross_validate(case_filename: str, annotation: dict) -> ForumResult:
    """Cross-validate a newly annotated case against related cross-platform cases.

    Args:
        case_filename: e.g. "case-034.md"
        annotation: dict with at least {severity, sentiment, platform}

    Returns:
        ForumResult with contradictions list and needs_review flag.
    """
    from engine.linker import find_related

    related = find_related(case_filename)
    if not related:
        return ForumResult(case_id=case_filename.replace(".md", ""))

    # Read related case annotations
    related_annotations = []
    for other_name, score in related:
        other_ann = _read_case_annotation(other_name)
        if other_ann:
            other_ann["linker_score"] = score
            related_annotations.append(other_ann)

    if not related_annotations:
        return ForumResult(case_id=case_filename.replace(".md", ""))

    # Check for contradictions without LLM first (simple heuristic)
    contradictions = _detect_contradictions_heuristic(annotation, related_annotations)

    # Only call Host LLM if heuristic found potential contradictions
    if contradictions:
        host_verdict = _call_host_llm(annotation, related_annotations, contradictions)
    else:
        host_verdict = ""

    return ForumResult(
        case_id=case_filename.replace(".md", ""),
        related_cases=[r["case_id"] for r in related_annotations],
        contradictions=contradictions,
        host_verdict=host_verdict,
        needs_review=len(contradictions) > 0,
    )


def _detect_contradictions_heuristic(
    current: dict, related: list[dict]
) -> list[str]:
    """Detect annotation contradictions using simple heuristics.

    Rules:
      1. Severity gap >= 2 levels (e.g. P0 vs P2)
      2. Opposite sentiment (正面 vs 负面) on same topic
    """
    issues = []
    sev_levels = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

    current_sev = current.get("severity", "")
    current_sent = current.get("sentiment", "")
    current_sev_num = sev_levels.get(current_sev, 99)

    for other in related:
        other_sev = other.get("severity", "")
        other_sent = other.get("sentiment", "")
        other_sev_num = sev_levels.get(other_sev, 99)

        # Check severity gap
        if current_sev_num != 99 and other_sev_num != 99:
            gap = abs(current_sev_num - other_sev_num)
            if gap >= 2:
                issues.append(
                    f"Severity gap: {current['case_id']}({current_sev}) on "
                    f"{current.get('platform','?')} vs "
                    f"{other['case_id']}({other_sev}) on {other.get('platform','?')}"
                )

        # Check sentiment opposite
        if current_sent and other_sent:
            opposite_pairs = [("正面", "负面"), ("负面", "正面")]
            if (current_sent, other_sent) in opposite_pairs:
                issues.append(
                    f"Sentiment conflict: {current['case_id']}({current_sent}) on "
                    f"{current.get('platform','?')} vs "
                    f"{other['case_id']}({other_sent}) on {other.get('platform','?')}"
                )

    return issues


def _call_host_llm(
    current: dict, related: list[dict], contradictions: list[str]
) -> str:
    """Call Host LLM to analyze cross-platform annotation contradictions."""
    system_prompt = _get_host_prompt()
    if not system_prompt:
        return ""

    # Build user prompt
    related_text = "\n".join(
        f"- [{r['case_id']}] platform={r['platform']} severity={r['severity']} "
        f"sentiment={r['sentiment']} title={r.get('title','')[:60]} "
        f"linker_score={r.get('linker_score','?'):.3f}"
        for r in related
    )
    contradictions_text = "\n".join(f"- {c}" for c in contradictions)

    user_msg = (
        f"当前案例 [{current.get('case_id','?')}]: "
        f"platform={current.get('platform','?')} "
        f"severity={current.get('severity','?')} "
        f"sentiment={current.get('sentiment','?')}\n\n"
        f"关联的跨平台案例:\n{related_text}\n\n"
        f"检测到的矛盾:\n{contradictions_text}\n\n"
        "请分析这些跨平台标注差异是否合理，是否需要人工复核。"
    )

    try:
        client, model = get_llm("deepseek")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Forum Host unavailable: {e}]"
