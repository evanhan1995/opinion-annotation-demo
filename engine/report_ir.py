# -*- coding: utf-8 -*-
"""Report IR — structured intermediate representation for daily/monthly reports.

Data flow:
  ReportData → build_ir() → fill_analysis() → validate_ir() → render_md() / render_html()

Design:
  - Code fills data_rows (numbers, tables, lists). LLM fills analysis text.
  - One LLM call per report, flat JSON, retry once on validation failure.
  - MD and HTML render from the same IR — single source of truth.
"""
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = PROJECT_ROOT / "wiki"
REPORTS_DAILY_DIR = WIKI_DIR / "reports" / "daily"
REPORTS_MONTHLY_DIR = WIKI_DIR / "reports" / "monthly"
PLOTLY_JS_CACHE: Optional[str] = None

# ── Data structures ─────────────────────────────────────────────────────

@dataclass
class Chapter:
    """Report chapter. data_rows filled by code; analysis filled by LLM."""
    anchor: str
    title: str
    data_rows: dict
    analysis: str = ""
    chart: dict | None = None


@dataclass
class ReportIR:
    """Intermediate representation of a report."""
    report_type: str  # "daily" | "monthly"
    date: str
    intro: str = ""
    chapters: list[Chapter] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ── Helpers ─────────────────────────────────────────────────────────────

def _pct(dist: dict, key: str) -> int:
    total = sum(dist.values())
    if total == 0:
        return 0
    return round(dist.get(key, 0) / total * 100)


def _trend(current: int, avg: float) -> str:
    if avg == 0:
        return "→"
    diff = (current - avg) / avg
    if diff > 0.1:
        return "↑"
    elif diff < -0.1:
        return "↓"
    return "→"


# ── Module builders registry（模板锚点 → 数据绑定） ──────────────────────
# 模板 JSON 只存锚点 key；数据如何绑定由内置注册表决定。
# （与 render_kind="custom" 走 RENDERER_REGISTRY 白名单同理：模板不携带可执行引用。）

def _build_volume(data, report_type):
    avg = getattr(data, "avg_prev_7days", 0.0)
    return ({"total_new_cases": data.total_new_cases, "avg_prev_7days": avg,
             "trend": _trend(data.total_new_cases, avg)}, None)


def _build_sentiment(data, report_type):
    pos_n = data.sentiment_dist.get("正面", 0)
    neu_n = data.sentiment_dist.get("中性", 0)
    neg_n = data.sentiment_dist.get("负面", 0)
    return ({"positive_pct": _pct(data.sentiment_dist, "正面"),
             "neutral_pct": _pct(data.sentiment_dist, "中性"),
             "negative_pct": _pct(data.sentiment_dist, "负面"),
             "positive_n": pos_n, "neutral_n": neu_n, "negative_n": neg_n},
            {"type": "pie", "labels": ["正面", "中性", "负面"], "values": [pos_n, neu_n, neg_n]})


def _build_top_issues(data, report_type):
    return ({"items": data.top_issues}, None)


def _build_severity(data, report_type):
    sevs = ["P0", "P1", "P2", "P3"]
    dr = {}
    for s in sevs:
        dr[f"{s.lower()}_count"] = data.severity_dist.get(s, 0)
        dr[f"{s.lower()}_pct"] = _pct(data.severity_dist, s)
    dr["p0p1_events"] = data.p0_p1_list
    return (dr, {"type": "bar", "labels": sevs,
                 "values": [data.severity_dist.get(s, 0) for s in sevs]})


def _build_platform(data, report_type):
    platforms = list(data.platform_dist.keys())
    return ({"platforms": data.platform_dist},
            {"type": "bar", "labels": platforms,
             "values": [data.platform_dist[p] for p in platforms]})


def _build_disposition(data, report_type):
    return ({"pending": data.status_dist.get("待跟进", 0),
             "in_progress": data.status_dist.get("处理中", 0),
             "done": data.status_dist.get("已处理", 0),
             "abandoned": data.status_dist.get("已放弃", 0),
             "ignored": data.status_dist.get("忽略", 0)}, None)


def _build_efficiency(data, report_type):
    return ({"avg_processing_time": data.status_dist.get("avg_processing_time", "暂无"),
             "completion_rate": data.status_dist.get("completion_rate", "暂无"),
             "p0_24h_rate": data.status_dist.get("p0_24h_rate", "暂无"),
             "p1_24h_rate": data.status_dist.get("p1_24h_rate", "暂无")}, None)


def _build_suggestions(data, report_type):
    return ({"top_issues": data.top_issues, "p0p1_list": data.p0_p1_list}, None)


MODULE_BUILDERS = {
    "volume-overview": _build_volume,
    "sentiment": _build_sentiment,
    "top-issues": _build_top_issues,
    "severity": _build_severity,
    "platform": _build_platform,
    "disposition": _build_disposition,
    "efficiency": _build_efficiency,
    "suggestions": _build_suggestions,
}


def build_ir(data, report_type) -> ReportIR:
    """Build IR skeleton from ReportData via a template.

    Args:
        data: ReportData (from agents.daily_report._collect_report_data)
        report_type: "daily" | "monthly"，或 ReportTemplate 实例。

    Returns ReportIR with data_rows populated and analysis fields empty.
    模板信息（template_id/version/llm_anchors）写入 ir.metadata。
    """
    from engine.report_model import default_template, ReportTemplate
    template = report_type if isinstance(report_type, ReportTemplate) else default_template(report_type)

    ir = ReportIR(
        report_type=template.template_type,
        date=data.date,
        metadata={
            "generator": "舆情标注Wiki",
            "generated_at": datetime.now().isoformat(),
            "template_id": template.template_id,
            "template_version": template.version,
            "llm_anchors": template.llm_anchors(),
        },
    )

    for m in template.sorted_modules():
        builder = MODULE_BUILDERS.get(m.anchor)
        if builder is None:
            continue
        data_rows, chart = builder(data, template.template_type)
        ir.chapters.append(Chapter(anchor=m.anchor, title=m.title, data_rows=data_rows, chart=chart))

    return ir


# ── fill_analysis (LLM) ─────────────────────────────────────────────────

_LLM_ANCHORS_DAILY = {"volume-overview", "sentiment", "disposition"}
_LLM_ANCHORS_MONTHLY = {"volume-overview", "sentiment", "severity", "disposition",
                        "efficiency", "suggestions"}


def _resolve_llm_anchors(ir: ReportIR) -> set:
    """从 ir.metadata 读模板定义的 LLM 锚点；缺失时回退历史常量（兼容手工构造的 IR）。"""
    anchors = (ir.metadata or {}).get("llm_anchors")
    if anchors:
        return set(anchors)
    return _LLM_ANCHORS_MONTHLY if ir.report_type == "monthly" else _LLM_ANCHORS_DAILY


def fill_analysis(ir: ReportIR, retry_hint: list[str] | None = None) -> ReportIR:
    """Call LLM once to fill all chapter.analysis fields and ir.intro.

    Args:
        ir: ReportIR with data_rows populated, analysis empty.
        retry_hint: If set, include previous errors in the prompt for correction.

    Returns the same ReportIR with analysis fields filled (mutates in place).
    """
    from agents.shared import get_llm, extract_json

    llm_anchors = _resolve_llm_anchors(ir)
    need_llm = [ch for ch in ir.chapters if ch.anchor in llm_anchors]

    # Compact data context
    ctx_lines = [f"日期：{ir.date}，报告类型：{'月报' if ir.report_type == 'monthly' else '日报'}"]
    for ch in need_llm:
        ctx_lines.append(f"\n[{ch.anchor}] {ch.title}")
        for k, v in ch.data_rows.items():
            if isinstance(v, list):
                if v and isinstance(v[0], dict):
                    ctx_lines.append(f"  {k}: " + "; ".join(
                        f"{d.get('title','?')}({d.get('severity','?')})" for d in v[:5]))
                elif v and isinstance(v[0], str):
                    ctx_lines.append(f"  {k}: {', '.join(v[:5])}")
            elif not isinstance(v, dict):
                ctx_lines.append(f"  {k}: {v}")

    # Anchor list for JSON format
    anchor_list = [ch.anchor for ch in need_llm]
    chapters_json_example = {a: "分析文本..." for a in anchor_list}

    hint_text = ""
    if retry_hint:
        hint_text = f"\n\n⚠️ 上次生成的问题：\n" + "\n".join(f"- {h}" for h in retry_hint)
        hint_text += "\n请修正上述问题后重新生成。"

    prompt = f"""根据以下舆情统计数据，为报告各章节生成分析文本（2-4句中文）。

数据上下文：
{chr(10).join(ctx_lines)}

要求：
1. 输出严格 JSON，格式如下，不要多也不要少key：
{{"intro": "一句话导语（日报用今日要点，月报用月度要览）",
  "chapters": {json_dumps(chapters_json_example, ensure_ascii=False)}
}}
2. 每个分析文本 2-4 句自然中文，语气专业客观，面向企业舆情管理团队
3. 关键数字可引用 data_rows 中的值，用自然语言融入分析
4. 突出异常变化和趋势判断（上升/下降/持平及原因推测）
5. 月报需额外判断环比变化趋势
6. 不要输出 Markdown 格式，纯文本即可
7. 只输出 JSON，不要额外解释{hint_text}"""

    # 补 wall-clock 超时：Daily Report 的 LLM 调用此前是裸调用（无超时保护），
    # 失败/超时记录降级状态并抛异常 → 外层 _build_ir_and_markdown 走模板回退。
    from engine._compat import call_with_timeout
    from engine.model_degradation import record_llm_failure, record_llm_success
    client, model = get_llm("deepseek")

    def _call():
        return client.chat.completions.create(
            model=model,
            max_tokens=1536 if ir.report_type == "monthly" else 1024,
            temperature=0.4,
            timeout=90,
            messages=[{"role": "user", "content": prompt}],
        )

    response, err = call_with_timeout(_call, 90)
    if err:
        record_llm_failure("daily_report", err)
        raise RuntimeError(f"日报 LLM 调用失败: {err}")
    record_llm_success("daily_report")
    raw = response.choices[0].message.content

    try:
        result = extract_json(raw)
    except Exception:
        import json
        result = json.loads(raw)

    ir.intro = result.get("intro", "")
    chapters_map = result.get("chapters", {})
    for ch in ir.chapters:
        if ch.anchor in chapters_map:
            ch.analysis = str(chapters_map[ch.anchor])

    return ir


def json_dumps(obj, **kw):
    """Local json.dumps wrapper to avoid shadowing the import."""
    import json as _json
    return _json.dumps(obj, **kw)


# ── validate_ir ─────────────────────────────────────────────────────────

def validate_ir(ir: ReportIR) -> tuple[bool, list[str]]:
    """Validate IR structure and content quality.

    Checks:
      1. intro non-empty and ≥10 chars
      2. Each LLM chapter's analysis non-empty, ≥20 chars
      3. No residual {{ }} placeholders or TODO markers

    Returns (is_valid, list_of_errors).
    """
    errors = []
    llm_anchors = _resolve_llm_anchors(ir)
    min_analysis = 20
    min_intro = 10

    if not ir.intro or len(ir.intro.strip()) < min_intro:
        errors.append(f"intro 缺失或过短（<{min_intro}字）: {ir.intro[:30] if ir.intro else '(空)'}")

    for ch in ir.chapters:
        if ch.anchor not in llm_anchors:
            continue
        a = (ch.analysis or "").strip()
        if not a:
            errors.append(f"chapter.{ch.anchor}.analysis 为空")
        elif len(a) < min_analysis:
            errors.append(f"chapter.{ch.anchor}.analysis 过短({len(a)}字，需≥{min_analysis}字)")
        if "{{" in a or "}}" in a:
            errors.append(f"chapter.{ch.anchor}.analysis 含残留占位符 {{}}")
        if "TODO" in a.upper() and "TODOs" not in a:
            errors.append(f"chapter.{ch.anchor}.analysis 含 TODO 标记")

    return len(errors) == 0, errors


# ── render_md ───────────────────────────────────────────────────────────

def render_md(ir: ReportIR) -> str:
    """Render ReportIR to Markdown string."""
    label = "舆情日报" if ir.report_type == "daily" else "舆情月报"
    lines = [f"# {label} {ir.date}", "", f"{ir.intro}", "",
             "─" * 50, ""]

    for ch in ir.chapters:
        lines.append(f"## {ch.title}")

        if ch.anchor == "volume-overview":
            dr = ch.data_rows
            lines.append(f"当日新增案例 **{dr['total_new_cases']}** 条，"
                         f"较前7日均值（{dr['avg_prev_7days']} 条）{dr['trend']}。")
            if ch.analysis:
                lines.append("")
                lines.append(ch.analysis)

        elif ch.anchor == "sentiment":
            dr = ch.data_rows
            lines.append(f"正面 **{dr['positive_pct']}%** | 中性 **{dr['neutral_pct']}%** | 负面 **{dr['negative_pct']}%**")
            if ch.analysis:
                lines.append("")
                lines.append(ch.analysis)

        elif ch.anchor == "top-issues":
            items = ch.data_rows.get("items", [])
            for i, item in enumerate(items, 1):
                lines.append(f"{i}. {item}")

        elif ch.anchor == "severity":
            dr = ch.data_rows
            lines.append("| 级别 | 数量 | 占比 |")
            lines.append("|------|------|------|")
            for s in ["p0", "p1", "p2", "p3"]:
                lines.append(f"| {s.upper()} | {dr[f'{s}_count']} | {dr[f'{s}_pct']}% |")
            if ch.analysis:
                lines.append("")
                lines.append(ch.analysis)
            events = dr.get("p0p1_events", [])
            if events:
                lines.append("")
                lines.append("### P0/P1 重点事件")
                for ev in events:
                    lines.append(f"- [{ev.get('severity', '?')}] {ev.get('title', '?')}（{ev.get('platform', '?')}）— {ev.get('status', '?')}")

        elif ch.anchor == "platform":
            platforms = ch.data_rows.get("platforms", {})
            for plat, count in platforms.items():
                lines.append(f"- {plat}：{count} 条")

        elif ch.anchor == "disposition":
            dr = ch.data_rows
            lines.append(f"- 待跟进：**{dr['pending']}** | 处理中：**{dr['in_progress']}** | "
                         f"已处理：**{dr['done']}**")
            lines.append(f"- 已放弃：**{dr['abandoned']}** | 忽略：**{dr['ignored']}**")
            if ch.analysis:
                lines.append("")
                lines.append(ch.analysis)

        elif ch.anchor == "efficiency":
            dr = ch.data_rows
            lines.append(f"- 平均处理时长：{dr['avg_processing_time']}")
            lines.append(f"- 处置完成率：{dr['completion_rate']}%")
            lines.append(f"- 24小时内处置率：P0 {dr['p0_24h_rate']}% | P1 {dr['p1_24h_rate']}%")
            if ch.analysis:
                lines.append("")
                lines.append(ch.analysis)

        elif ch.anchor == "suggestions":
            if ch.analysis:
                lines.append(ch.analysis)

        lines.append("")

    lines.extend(["─" * 50, "",
                  f"*本报告由{ir.metadata.get('generator', '舆情标注Wiki')}自动生成于 {ir.date}*"])
    return "\n".join(lines)


# ── render_html ─────────────────────────────────────────────────────────

_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
       background: #f0f2f5; color: #333; line-height: 1.6; }
.cover { background: linear-gradient(135deg, #1a3a5c 0%, #2d6a9f 100%);
         color: white; padding: 50px 40px; text-align: center; border-radius: 0 0 16px 16px; }
.cover h1 { font-size: 2em; margin-bottom: 6px; letter-spacing: 2px; }
.cover .subtitle { font-size: 1.1em; opacity: 0.85; margin-bottom: 24px; }
.cover .divider { width: 60px; height: 3px; background: rgba(255,255,255,0.5); margin: 0 auto 24px; }
.cover .generator { font-size: 0.85em; opacity: 0.6; }
.metrics { display: grid; grid-template-columns: repeat(4, 1fr);
           gap: 14px; padding: 24px 36px; max-width: 960px; margin: -24px auto 0; }
.card { background: white; border-radius: 10px; padding: 18px 14px; text-align: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06); }
.card .value { font-size: 1.8em; font-weight: 700; color: #1a3a5c; }
.card .label { font-size: 0.8em; color: #999; margin-top: 4px; }
.card.warn .value { color: #d62728; }
.card.good .value { color: #2ca02c; }
.container { max-width: 960px; margin: 0 auto; padding: 20px 36px 36px; }
.chart-box { background: white; border-radius: 10px; padding: 18px; margin-bottom: 16px;
             box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
.chart-box h2 { font-size: 1.1em; color: #1a3a5c; margin-bottom: 8px;
                border-left: 4px solid #2d6a9f; padding-left: 10px; }
.alert-box { background: #fff5f5; border-left: 4px solid #d62728; border-radius: 6px;
             padding: 14px 18px; margin-bottom: 16px; }
.alert-box h3 { color: #d62728; margin-bottom: 6px; font-size: 1em; }
.footer { text-align: center; padding: 16px; color: #bbb; font-size: 0.78em; }
@media print {
  body { background: white; }
  .cover { border-radius: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .card { box-shadow: none; border: 1px solid #eee; break-inside: avoid; }
  .chart-box { box-shadow: none; border: 1px solid #eee; break-inside: avoid; }
  .metrics { break-inside: avoid; }
  @page { margin: 12mm; }
}
"""


def _read_plotly_min_js() -> str:
    """Read Plotly.min.js from installed plotly package, cached."""
    global PLOTLY_JS_CACHE
    if PLOTLY_JS_CACHE is not None:
        return PLOTLY_JS_CACHE
    import plotly as _p
    import os
    _p_dir = os.path.dirname(_p.__file__)
    _js_path = Path(_p_dir) / "package_data" / "plotly.min.js"
    PLOTLY_JS_CACHE = _js_path.read_text(encoding="utf-8")
    return PLOTLY_JS_CACHE


def _render_metric_cards(ir: ReportIR) -> str:
    """Render 4 KPI metric cards as HTML."""
    vol = ir.chapters[0].data_rows if ir.chapters else {}
    sent = ir.chapters[1].data_rows if len(ir.chapters) > 1 else {}
    sev = ir.chapters[3].data_rows if len(ir.chapters) > 3 else {}

    total = vol.get("total_new_cases", 0)
    avg = vol.get("avg_prev_7days", 0)
    p0p1 = sev.get("p0_count", 0) + sev.get("p1_count", 0)
    neg_pct = sent.get("negative_pct", 0)

    cards_data = [
        ("案例总数", total, ""),
        ("前7日均值", str(avg), ""),
        ("P0/P1 高危", p0p1, "warn"),
        ("负面占比", f"{neg_pct}%", "warn" if neg_pct > 30 else "good"),
    ]
    lines = ['<div class="metrics">']
    for label, value, cls in cards_data:
        lines.append(f'<div class="card {cls}"><div class="value">{value}</div><div class="label">{label}</div></div>')
    lines.append('</div>')
    return "\n".join(lines)


def _plot_sentiment_pie(ir: ReportIR) -> str:
    """Plotly pie chart from IR sentiment chapter."""
    ch = next((c for c in ir.chapters if c.anchor == "sentiment"), None)
    if not ch or not ch.chart:
        return ""
    import plotly.graph_objects as go
    colors = {"正面": "#2ca02c", "中性": "#7f7f7f", "负面": "#d62728"}
    labels = ch.chart["labels"]
    values = ch.chart["values"]
    if not values or sum(values) == 0:
        return ""
    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values,
        marker=dict(colors=[colors.get(l, "#1f77b4") for l in labels]),
        textinfo="label+percent",
    )])
    fig.update_layout(height=400)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _plot_severity_bar(ir: ReportIR) -> str:
    """Plotly bar chart from IR severity chapter."""
    ch = next((c for c in ir.chapters if c.anchor == "severity"), None)
    if not ch or not ch.chart:
        return ""
    values = ch.chart["values"]
    if not values or sum(values) == 0:
        return ""
    import plotly.graph_objects as go
    colors = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4"]
    labels = ch.chart["labels"]
    fig = go.Figure(data=[go.Bar(x=labels, y=values, marker_color=colors,
                                  text=values, textposition="auto")])
    fig.update_layout(height=400, xaxis_title="严重等级", yaxis_title="案例数")
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _plot_platform_bar(ir: ReportIR) -> str:
    """Plotly bar chart from IR platform chapter."""
    ch = next((c for c in ir.chapters if c.anchor == "platform"), None)
    if not ch or not ch.chart:
        return ""
    values = ch.chart["values"]
    if not values or sum(values) == 0:
        return ""
    import plotly.graph_objects as go
    labels = ch.chart["labels"]
    fig = go.Figure(data=[go.Bar(x=labels, y=values, marker_color="#1f77b4",
                                  text=values, textposition="auto")])
    fig.update_layout(height=400, xaxis_title="平台", yaxis_title="案例数")
    return fig.to_html(full_html=False, include_plotlyjs=False)


def render_html(ir: ReportIR) -> str:
    """Render ReportIR to a complete offline HTML document with Plotly charts."""
    title = "舆情监测日报" if ir.report_type == "daily" else "舆情监测月报"
    cover_date = ir.date
    if ir.report_type == "monthly":
        cover_date = ir.date[:7] if len(ir.date) > 7 else ir.date

    p0p1_count = 0
    sev_ch = next((c for c in ir.chapters if c.anchor == "severity"), None)
    if sev_ch:
        p0p1_count = sev_ch.data_rows.get("p0_count", 0) + sev_ch.data_rows.get("p1_count", 0)

    cards = _render_metric_cards(ir)

    charts = ""
    pie = _plot_sentiment_pie(ir)
    if pie:
        charts += f'<div class="chart-box"><h2>情感分布</h2>{pie}</div>\n'
    charts += f'<div class="chart-box"><h2>严重度分布</h2>{_plot_severity_bar(ir)}</div>\n'
    plat = _plot_platform_bar(ir)
    if plat:
        charts += f'<div class="chart-box"><h2>平台分布</h2>{plat}</div>\n'

    # Alert box for P0/P1
    alert_content = "暂无高危事件" if p0p1_count == 0 else f"共 {p0p1_count} 条高危事件需要关注，请及时处置。"
    alert_html = f'<div class="alert-box"><h3>P0/P1 高危事件 (共 {p0p1_count} 条)</h3><p>{alert_content}</p></div>'

    plotly_js = _read_plotly_min_js()

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{title} {cover_date}</title>
<style>{_CSS}</style></head>
<body>
<div class="cover">
  <h1>{title}</h1>
  <div class="subtitle">{cover_date}</div>
  <div class="divider"></div>
  <div class="generator">舆情标注Wiki · 自动化舆情监测系统</div>
</div>
{cards}
<div class="container">
{charts}
{alert_html}
<div class="footer">舆情标注Wiki · 自动生成于 {ir.date} · 仅供内部参考</div>
</div>
<script>{plotly_js}</script>
</body>
</html>"""


# ── Convenience: full pipeline ──────────────────────────────────────────

def generate_report(data, report_type: str, max_retries: int = 1) -> tuple[ReportIR, str, str]:
    """Run full IR pipeline: build → LLM fill → validate → render.

    Args:
        data: ReportData from _collect_report_data.
        report_type: "daily" or "monthly".
        max_retries: Max LLM retries on validation failure (default 1).

    Returns (ReportIR, markdown_str, html_str).

    Raises RuntimeError if validation fails after all retries.
    """
    ir = build_ir(data, report_type)
    ir = fill_analysis(ir)
    ok, errors = validate_ir(ir)

    for attempt in range(max_retries):
        if ok:
            break
        ir = fill_analysis(ir, retry_hint=errors)
        ok, errors = validate_ir(ir)

    if not ok:
        raise RuntimeError(f"IR validation failed after {max_retries} retries: {errors}")

    md = render_md(ir)
    html = render_html(ir)
    return ir, md, html
