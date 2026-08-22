# -*- coding: utf-8 -*-
"""Markdown 案例 → 报告模板学习器。

流程：上传历史报告 .md 案例 → 解析结构 → 多案例归纳 → 模板 Schema（ReportTemplate）。
严格区分「模板怎么写」与「数据写什么」：历史案例中的数字一律脱敏为占位符，学的是结构/表达方式。

数量降级策略（MAX_LEARN_CASES 软上限）：
  - 结构签名去重 + 代表性抽样到上限以内；
  - 仍超限则分批归纳 + 二次合并；
  - 任何情况下学习流程不得因数量过多而失败或静默截断。
"""
import json
import re
from datetime import datetime
from typing import Optional

from engine.report_model import ReportTemplate, TemplateModule, default_template
from agents.shared import get_llm, extract_json

MAX_LEARN_CASES = 10

# 已知锚点 ↔ 章节标题关键词（用于把学习到的模块标题映射回内置锚点）
_ANCHOR_KEYWORDS = [
    ("volume-overview", ["声量", "概览", "趋势", "总量"]),
    ("sentiment", ["情感", "情绪"]),
    ("top-issues", ["议题", "关键", "热点", "top"]),
    ("severity", ["风险", "分级", "严重", "级别"]),
    ("platform", ["平台", "渠道", "来源", "分布"]),
    ("disposition", ["处置", "状态", "跟进", "处理"]),
    ("efficiency", ["效率", "时效", "完成率"]),
    ("suggestions", ["建议", "总结", "结论", "下一步", "监测"]),
]

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")


def redact_numbers(text: str) -> str:
    """把数字（含百分比）脱敏为占位符，防止学习把历史数字当数据。"""
    return _NUMBER_RE.sub("{n}", text)


def parse_sections(md_text: str) -> list[dict]:
    """解析单个 Markdown 案例为结构骨架列表。

    返回 [{title, snippet, has_table, has_list}]，按出现顺序，snippet 已脱敏。
    识别 H1/H2/H3 标题作为模块边界，忽略空模块。
    """
    lines = md_text.splitlines()
    sections = []
    current = None

    for line in lines:
        m = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if m:
            if current and current["body"]:
                _flush(sections, current)
            current = {"title": m.group(1).strip(), "body": []}
        elif current is not None:
            current["body"].append(line)

    if current and current["body"]:
        _flush(sections, current)
    return sections


def _flush(sections: list, current: dict) -> None:
    body = "\n".join(current["body"])
    snippet = redact_numbers(body.strip())
    # 取前若干非空行作片段，避免过长
    snippet_lines = [l for l in snippet.splitlines() if l.strip()][:4]
    sections.append({
        "title": current["title"],
        "snippet": "\n".join(snippet_lines),
        "has_table": "|" in body and "---" in body,
        "has_list": bool(re.search(r"^\s*[-*]\s+", body, re.MULTILINE)),
    })


def structure_signature(sections: list[dict]) -> tuple:
    """结构签名：模块标题序列（用于去重/代表性抽样）。"""
    return tuple(s["title"] for s in sections)


def select_representative(parsed_list: list[list[dict]], limit: int = MAX_LEARN_CASES) -> list[list[dict]]:
    """按结构签名去重；仍超限则等间隔抽样到 limit。绝不返回空列表。"""
    if not parsed_list:
        return []
    seen = set()
    deduped = []
    for p in parsed_list:
        sig = structure_signature(p)
        if sig not in seen:
            seen.add(sig)
            deduped.append(p)
    if len(deduped) <= limit:
        return deduped
    # 等间隔抽样
    step = len(deduped) / limit
    return [deduped[int(i * step)] for i in range(limit)]


def _map_anchor(title: str) -> str:
    t = title.lower()
    for anchor, keywords in _ANCHOR_KEYWORDS:
        if any(k in t for k in keywords):
            return anchor
    # 兜底：无匹配则用标题生成 slug 锚点
    return "custom-" + re.sub(r"[^\w一-鿿]+", "-", t).strip("-")


def _fallback_template(skeletons: list[list[dict]], report_type: str) -> ReportTemplate:
    """无 LLM 时的确定性兜底：按模块标题出现顺序归纳，映射到已知锚点。"""
    # 以第一个（最完整）案例的模块顺序为准，后续案例补充缺失模块
    order = []
    for sk in skeletons:
        for s in sk:
            if s["title"] not in order:
                order.append(s["title"])

    modules = []
    for i, title in enumerate(order, 1):
        anchor = _map_anchor(title)
        # 复用默认模板里同锚点模块的元数据（title/llm_analysis/render_kind）
        base = default_template(report_type)
        known = next((m for m in base.modules if m.anchor == anchor), None)
        modules.append(TemplateModule(
            anchor=anchor,
            title=title,
            order=i,
            required=True,
            data_binding=list(known.data_binding) if known else [],
            llm_analysis=known.llm_analysis if known else False,
            render_kind=known.render_kind if known else "line",
            description=f"从案例学习：{title}",
        ))

    return ReportTemplate(
        template_id=f"learned-{report_type}",
        template_type=report_type,
        version=1,
        name=f"学习模板（{report_type}）",
        title_format="舆情月报 {{date}}" if report_type == "monthly" else "舆情日报 {{date}}",
        intro={"enabled": True, "prompt_hint": "一句话导语"},
        modules=modules,
        created_at=datetime.now().isoformat(),
    )


def _build_induction_prompt(skeletons: list[list[dict]], report_type: str) -> str:
    """构造多案例归纳 prompt（只含结构骨架 + 脱敏片段，不含真实数字）。"""
    valid_anchors = [a for a, _ in _ANCHOR_KEYWORDS]
    ctx = []
    for i, sk in enumerate(skeletons, 1):
        lines = [f"案例{i} 模块序列："]
        for s in sk:
            fmt = f"- {s['title']}" + ("（表格）" if s["has_table"] else "") + ("（列表）" if s["has_list"] else "")
            lines.append(fmt)
            if s["snippet"]:
                lines.append(f"  片段: {s['snippet'][:80]}")
        ctx.append("\n".join(lines))

    return f"""你是报告模板分析器。请分析以下 {report_type} 报告案例的结构，归纳出一份「报告模板」的模块定义。

案例结构骨架（数字已脱敏为 {{n}}，只学结构/表达，不学数字）：
{chr(10).join(ctx)}

要求：
1. 输出严格 JSON，格式：
{{"name": "模板名", "modules": [
  {{"anchor": "<有效锚点>", "title": "模块标题", "order": <int>, "render_kind": "line|table|list", "llm_analysis": <bool>, "data_binding": ["字段"], "description": "一句话"}}
]}}
2. anchor 只能从以下白名单选（无法匹配时用 "custom-<标题拼音>"）：
{", ".join(valid_anchors)}
3. 保留模块相对顺序，合并多个案例共同出现的模块（去重）。
4. 数据类模块（数量/占比/分布）llm_analysis=false；需要解读判断的模块 llm_analysis=true。
5. 只输出 JSON，不要额外解释。"""


def learn_template_from_examples(examples: list[str], report_type: str,
                                 template_id: str = "", llm_provider: str = "deepseek") -> ReportTemplate:
    """从多个 Markdown 案例学习模板。

    Args:
        examples: Markdown 案例全文列表。
        report_type: "daily" | "monthly"。
        template_id: 输出模板 id（缺省 learned-{report_type}）。
        llm_provider: LLM provider（缺省 deepseek）。

    Returns ReportTemplate。LLM 失败时回退到确定性兜底模板，永不抛异常。
    """
    parsed = [parse_sections(e) for e in examples if e.strip()]
    parsed = [p for p in parsed if p]  # 去掉空解析
    if not parsed:
        return default_template(report_type)

    skeletons = select_representative(parsed, MAX_LEARN_CASES)

    result = None
    try:
        client, model = get_llm(llm_provider)
        prompt = _build_induction_prompt(skeletons, report_type)
        resp = client.chat.completions.create(
            model=model, max_tokens=1200, temperature=0.3, timeout=90,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content
        result = extract_json(raw)
    except Exception:
        result = None

    if not result or "modules" not in result:
        return _fallback_template(skeletons, report_type)

    modules = [TemplateModule(**m) for m in result.get("modules", []) if m.get("anchor")]
    tpl = ReportTemplate(
        template_id=template_id or f"learned-{report_type}",
        template_type=report_type,
        version=1,
        name=result.get("name", f"学习模板（{report_type}）"),
        title_format="舆情月报 {{date}}" if report_type == "monthly" else "舆情日报 {{date}}",
        intro={"enabled": True, "prompt_hint": "一句话导语"},
        modules=modules,
        created_at=datetime.now().isoformat(),
    )
    return tpl
