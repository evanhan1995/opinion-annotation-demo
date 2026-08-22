# -*- coding: utf-8 -*-
"""统一报告渲染器。

报告 Tab 与飞书都从同一个 FinalReport（engine.report_model.FinalReport）渲染，
不再各自生成内容。本模块只做"结构化 IR → 目标格式"的技术转换：
  - render_web  → 直接返回缓存好的 markdown
  - render_feishu → 紧凑但完整地映射为 lark_md 卡片（模块/顺序/数据行/P0P1 全量一致）

一致性口径：数据行、P0/P1 事件、关键议题等结构化条目数量与报告 Tab 一致；
分析文字允许因紧凑渲染而省略（不要求逐字一致）。
"""
from typing import Optional

from engine.report_model import report_dir

# 每模块在飞书卡片中的详细度：data_only=只渲染数据行；full=数据行 + LLM 分析段。
# 这是显式配置结构（非函数内 if/else 硬判断）；未来模板系统可通过
# TemplateModule.feishu_verbosity 覆盖它（render_feishu 的 verbosity 参数已留口子）。
MODULE_FEISHU_VERBOSITY = {
    "volume-overview": "full",   # 声量概览（含趋势判断）
    "sentiment": "data_only",
    "top-issues": "data_only",
    "severity": "data_only",     # 数据行 + p0p1_events 全量
    "platform": "data_only",
    "disposition": "full",       # 处置状态（含积压分析）
    "efficiency": "data_only",
    "suggestions": "full",
}

# 飞书 Interactive Card 物理上限（软阈值，超限触发二级降级，绝不静默截断）
FEISHU_MAX_CHARS = 4000   # body 字符软上限
FEISHU_MAX_P0P1 = 20      # P0/P1 全量条数软上限


def render_web(final_report) -> str:
    """Web 渲染：直接返回缓存好的 markdown（与 .md 文件一致）。"""
    return final_report.markdown


def render_feishu(final_report, verbosity: Optional[dict] = None) -> tuple[str, str, Optional[dict]]:
    """把 FinalReport 映射为飞书卡片。返回 (title, body_text, fields)。

    verbosity: {anchor: "data_only"|"full"} 覆盖项，缺省合并 MODULE_FEISHU_VERBOSITY。
    """
    verbosity = {**MODULE_FEISHU_VERBOSITY, **(verbosity or {})}
    chapters = final_report.chapters()

    title = f"舆情{'月报' if final_report.report_type == 'monthly' else '日报'} — {final_report.report_date}"

    sections = []
    for ch in chapters:
        section = _render_chapter(ch, verbosity.get(ch.get("anchor", ""), "data_only"))
        if section:
            sections.append(section)

    body = "\n\n".join(sections)
    body = _degrade_if_oversize(final_report, body)

    return title, body, None


# ── 单模块渲染 ─────────────────────────────────────────────────────────

def _render_chapter(ch: dict, verbosity: str) -> str:
    """渲染单个章节：标题 + 数据行（全量） + 可选分析段。"""
    anchor = ch.get("anchor", "")
    title = ch.get("title", "")
    data_rows = ch.get("data_rows") or {}
    analysis = (ch.get("analysis") or "").strip()

    data_text = _format_chapter_data(anchor, data_rows)

    parts = [f"**{title}**"]
    if data_text:
        parts.append(data_text)
    if verbosity == "full" and analysis:
        parts.append(analysis)
    return "\n".join(parts)


def _format_chapter_data(anchor: str, dr: dict) -> str:
    """按模块锚点把 data_rows 格式化为紧凑文本。未知锚点用通用 key:value 兜底。"""
    if anchor == "volume-overview":
        return f"当日新增案例 {dr.get('total_new_cases', 0)} 条（近7日均值 {dr.get('avg_prev_7days', 0)} 条）{dr.get('trend', '')}".strip()

    if anchor == "sentiment":
        return f"正面 {dr.get('positive_pct', 0)}% | 中性 {dr.get('neutral_pct', 0)}% | 负面 {dr.get('negative_pct', 0)}%"

    if anchor == "top-issues":
        items = dr.get("items", [])
        if not items:
            return "（暂无数据）"
        return "\n".join(f"· {it}" for it in items)

    if anchor == "severity":
        line = f"P0 {dr.get('p0_count', 0)} | P1 {dr.get('p1_count', 0)} | P2 {dr.get('p2_count', 0)} | P3 {dr.get('p3_count', 0)}"
        events = dr.get("p0p1_events", [])
        if events:
            line += "\n" + _format_p0p1(events)
        return line

    if anchor == "platform":
        platforms = dr.get("platforms", {})
        if not platforms:
            return "（暂无数据）"
        return "、".join(f"{k} {v}" for k, v in platforms.items())

    if anchor == "disposition":
        return (f"待跟进 {dr.get('pending', 0)} | 处理中 {dr.get('in_progress', 0)} | 已处理 {dr.get('done', 0)}"
                f" | 已放弃 {dr.get('abandoned', 0)} | 忽略 {dr.get('ignored', 0)}")

    if anchor == "efficiency":
        return (f"平均处理时长 {dr.get('avg_processing_time', '暂无')}"
                f" | 完成率 {dr.get('completion_rate', '暂无')}%"
                f" | 24h处置率 P0 {dr.get('p0_24h_rate', '暂无')}% P1 {dr.get('p1_24h_rate', '暂无')}%")

    if anchor == "suggestions":
        # 建议模块以分析文本为主，数据行仅作参考，不重复展示
        return ""

    # 通用兜底：键值行
    return "\n".join(f"{k}: {v}" for k, v in dr.items() if not isinstance(v, (dict, list)))


def _format_p0p1(events: list[dict], max_events: Optional[int] = None) -> str:
    """渲染 P0/P1 事件全量。若 max_events 限制且超限，明确输出「另有 N 条未展开」。

    绝不静默丢弃：折叠时列出剩余条数提示。
    """
    if not events:
        return ""

    if max_events is None or len(events) <= max_events:
        return "\n".join(_p0p1_line(ev) for ev in events)

    shown = events[:max_events]
    hidden = len(events) - max_events
    lines = [_p0p1_line(ev) for ev in shown]
    lines.append(f"…另有 {hidden} 条未展开")
    return "\n".join(lines)


def _p0p1_line(ev: dict) -> str:
    """单条 P0/P1 事件行。标题不截断。"""
    severity = ev.get("severity", "?")
    title = ev.get("title", "?")
    platform = ev.get("platform", "?")
    return f"· [{severity}] {title}（{platform}）"


# ── 二级降级（物理上限） ───────────────────────────────────────────────

def _degrade_if_oversize(final_report, body: str) -> str:
    """飞书卡片超限时的二级降级：P0 全量 + P1 前 N + 提示 + 报告链接。绝不静默截断。"""
    if len(body) <= FEISHU_MAX_CHARS:
        return body

    # 定位 severity 章节的 p0p1_events，重排为 P0 全量 + P1 前 N
    sev_ch = next((c for c in final_report.chapters() if c.get("anchor") == "severity"), None)
    events = (sev_ch or {}).get("data_rows", {}).get("p0p1_events", []) if sev_ch else []
    p0 = [e for e in events if e.get("severity") == "P0"]
    p1 = [e for e in events if e.get("severity") == "P1"]

    # 保留全部 P0，P1 逐步收缩到 FEISHU_MAX_P0P1 以内
    p1_kept = p1[:FEISHU_MAX_P0P1]
    p1_hidden = len(p1) - len(p1_kept)

    lines = []
    if p0:
        lines.append("P0 事件：")
        lines.extend(_p0p1_line(e) for e in p0)
    if p1_kept:
        lines.append("P1 事件（部分）：")
        lines.extend(_p0p1_line(e) for e in p1_kept)
    if p1_hidden > 0:
        lines.append(f"…另有 {p1_hidden} 条 P1 未展开")

    link = report_dir(final_report.report_type) / f"{final_report.report_date}.md"
    lines.append(f"完整报告见 {link.name}（{final_report.report_type}/{final_report.report_date}）")

    return "⚠️ 报告内容较多，已收缩为高危事件概览。\n\n" + "\n".join(lines)
