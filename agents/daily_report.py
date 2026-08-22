# -*- coding: utf-8 -*-
"""
舆情指挥系统 — Daily Report Agent (日报组)

Responsibility (PRD §5.6):
  Generate daily reports (21:00) and monthly reports (1st 09:00).
  Input: structured query results from Curator + Monitor stats.
  Output: Markdown reports → wiki/reports/daily/ and wiki/reports/monthly/.

Isolation constraints:
  - MUST NOT modify any KB entries (read-only query)
  - MUST NOT modify case statuses or annotation results
  - Reads data through Curator.query_*() only, not direct file access

Model: MiniMax (Chinese text generation, cost-effective for high-volume output).
"""
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from engine.report_model import (
    FinalReport, save_final_report, make_report_id, get_active_template,
)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from agents.shared import (
    get_llm, PROJECT_ROOT, WIKI_DIR, OUTPUTS_DIR,
)

REPORTS_DAILY_DIR = WIKI_DIR / "reports" / "daily"
REPORTS_MONTHLY_DIR = WIKI_DIR / "reports" / "monthly"


# ── Report data structures ─────────────────────────────────────────────
@dataclass
class ReportData:
    """Structured data passed to Daily Report Agent for generation."""
    date: str
    total_new_cases: int = 0
    avg_prev_7days: float = 0.0
    sentiment_dist: dict = field(default_factory=lambda: {"正面": 0, "中性": 0, "负面": 0})
    top_issues: list[str] = field(default_factory=list)
    severity_dist: dict = field(default_factory=lambda: {"P0": 0, "P1": 0, "P2": 0, "P3": 0})
    platform_dist: dict = field(default_factory=dict)
    status_dist: dict = field(default_factory=dict)
    p0_p1_list: list[dict] = field(default_factory=list)
    monitor_stats: dict = field(default_factory=dict)


# ── Monitor stats helpers ───────────────────────────────────────────────
def _monitor_stats_path(date_str: str) -> Path:
    """monitor_stats 文件路径：outputs/monitor_stats_{YYYY-MM-DD}.json。"""
    return OUTPUTS_DIR / f"monitor_stats_{date_str}.json"


def _load_daily_monitor_stats(date_str: str) -> dict:
    """读取当天 monitor_stats 文件，返回 {监测关键词数, 去重率}。

    文件不存在（当天没跑 Monitor）返回空 dict —— 与「监测了但结果为 0」区分：
    空 dict 表示「无监测数据」，非空 dict 里的 0 才是真实统计结果。
    """
    path = _monitor_stats_path(date_str)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        "监测关键词数": payload.get("keywords_searched", 0),
        "去重率": payload.get("dedup_rate", 0.0),
    }


def _aggregate_monthly_monitor_stats(month_str: str) -> dict:
    """聚合当月所有 monitor_stats_{YYYY-MM-DD}.json，返回 {监测关键词数, 去重率}。

    口径：
      - 监测关键词数：当月所有天 keyword_ids 去重后的数量（不是逐天累加，
        否则同一关键词会被重复计数）。
      - 去重率：(Σ total_fetched - Σ total_new) / Σ total_fetched 重新计算，
        不对每日 dedup_rate 做简单平均（简单平均在每日样本量不同时会失真）。
    当月无任何监测文件返回空 dict（=无监测数据）。
    """
    files = sorted(OUTPUTS_DIR.glob(f"monitor_stats_{month_str}-*.json"))
    if not files:
        return {}
    total_fetched = 0
    total_new = 0
    keyword_ids: set = set()
    for f in files:
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        total_fetched += int(payload.get("total_fetched", 0) or 0)
        total_new += int(payload.get("total_new", 0) or 0)
        for kid in payload.get("keyword_ids", []) or []:
            keyword_ids.add(kid)
    dedup_rate = (total_fetched - total_new) / total_fetched if total_fetched > 0 else 0.0
    return {
        "监测关键词数": len(keyword_ids),
        "去重率": dedup_rate,
    }


def _monitor_section_md(monitor_stats: dict) -> str:
    """渲染「监测概况」章节。

    monitor_stats 为空 dict → 显示「无监测数据」；非空 → 显示真实数字。
    去重率格式化为百分比（与 ui/tab3_monitor.py 的 .0% 口径一致）。
    """
    lines = ["## 监测概况"]
    if not monitor_stats:
        lines.append("- 无监测数据")
    else:
        lines.append(f"- 监测关键词数：{monitor_stats.get('监测关键词数', 0)}")
        lines.append(f"- 去重率：{monitor_stats.get('去重率', 0.0):.0%}")
    return "\n".join(lines)


# ── Data collection ────────────────────────────────────────────────────
def _collect_report_data(date_str: str = "", month_str: str = "") -> ReportData:
    """Collect real metrics via Curator.query_cases() + query_stats().

    PRD §5.6: Daily Report reads KB data through Curator only — no direct
    file access. This is the SINGLE legal data path.

    Args:
        date_str: ISO date for daily report (e.g. "2026-05-24")
        month_str: ISO month for monthly report (e.g. "2026-05")
                   When provided, date_from/date_to are set to month boundaries.
    """
    from calendar import monthrange
    from agents.curator import query_cases, query_stats as curator_stats

    if month_str:
        # Monthly report: compute first/last day of the month
        year, month = int(month_str[:4]), int(month_str[5:7])
        last_day = monthrange(year, month)[1]
        date_from = f"{month_str}-01"
        date_to = f"{month_str}-{last_day:02d}T23:59:59"
        data = ReportData(date=month_str)
    else:
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        date_from = date_str
        date_to = date_str + "T23:59:59"
        data = ReportData(date=date_str)

    # 监测统计：日报读当天文件，月报读当月聚合；文件不存在则为空 dict（=无监测数据）。
    # 必须在「无案例早退」之前设置——Monitor 可能跑了但 0 条新增，此时仍应展示真实数据。
    if month_str:
        data.monitor_stats = _aggregate_monthly_monitor_stats(month_str)
    else:
        data.monitor_stats = _load_daily_monitor_stats(date_str)

    stats = curator_stats(date_from=date_from, date_to=date_to)
    if not stats["total_cases"]:
        return data

    data.severity_dist = stats["severity_dist"]
    data.sentiment_dist = stats["sentiment_dist"]
    data.platform_dist = stats["platform_dist"]
    data.status_dist = stats["status_dist"]
    data.p0_p1_list = stats["p0_p1_list"]
    data.top_issues = stats["top_categories"]

    data.total_new_cases = stats["total_cases"]

    # 7-day average (daily report only)
    if not month_str:
        seven_days_ago_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        week_cases = len(query_cases({"date_from": seven_days_ago_str}))
        data.avg_prev_7days = round(week_cases / 7, 1) if week_cases else 0.0

    return data


# ── Daily report ───────────────────────────────────────────────────────
def generate_daily(date_str: str = "") -> str:
    """Generate daily report from real case metrics. Returns path to report file.

    Phase 3: LLM generation via DeepSeek with template fallback.
    统一报告源：生成后缓存 FinalReport（.report.json），报告 Tab 与飞书同读。
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    data = _collect_report_data(date_str)
    template = get_active_template("daily")
    ir, markdown = _build_ir_and_markdown(data, template)

    try:
        from engine.report_ir import render_html
        html = render_html(ir)
    except Exception:
        html = ""

    fr = FinalReport(
        report_id=make_report_id("daily", date_str),
        report_type="daily",
        report_date=date_str,
        template_id=template.template_id,
        template_version=template.version,
        generated_at=datetime.now().isoformat(),
        status="published",
        data=asdict(data),
        ir=asdict(ir),
        markdown=markdown,
        html=html,
    )
    save_final_report(fr)

    return str(REPORTS_DAILY_DIR / f"{date_str}.md")


def _build_ir_and_markdown(data: ReportData, template) -> tuple:
    """Build ReportIR + markdown via the IR pipeline (LLM → validate → render).

    v7.1: Uses engine.report_ir for structured generation with schema validation.
    Falls back to template on LLM or validation failure.

    Returns (ReportIR, markdown_str). The IR is kept so the FinalReport can
    persist structured chapters for the Feishu renderer (single source of truth).
    """
    from engine.report_ir import build_ir, fill_analysis, validate_ir, render_md

    ir = build_ir(data, template)
    ok = False
    try:
        ir = fill_analysis(ir)
        ok, errors = validate_ir(ir)
        if not ok:
            ir = fill_analysis(ir, retry_hint=errors)
            ok, _ = validate_ir(ir)
    except Exception:
        ok = False

    if ok:
        md = render_md(ir)
    else:
        md = _build_daily_template(data) if template.template_type == "daily" else _build_monthly_template(data)

    # 追加「监测概况」章节（IR 渲染路径与模板回退路径统一在这里追加，
    # 保证两种路径的日报/月报都展示真实监测数据或「无监测数据」）。
    md = md.rstrip() + "\n\n" + _monitor_section_md(data.monitor_stats) + "\n"
    return ir, md


def _build_daily_template(data: ReportData) -> str:
    """Template-based fallback for daily report."""
    return f"""# 舆情日报 {data.date}

## 一、声量概览
- 当日案例总数：{data.total_new_cases} 条（前7日均值：{data.avg_prev_7days} 条）

## 二、情感分布
- 正面：{_pct(data.sentiment_dist, '正面')}% | 中性：{_pct(data.sentiment_dist, '中性')}% | 负面：{_pct(data.sentiment_dist, '负面')}%

## 三、关键议题TOP5
{_list_as_md(data.top_issues)}

## 四、风险分级
- P0：{data.severity_dist.get('P0', 0)} 条 | P1：{data.severity_dist.get('P1', 0)} 条 | P2：{data.severity_dist.get('P2', 0)} 条 | P3：{data.severity_dist.get('P3', 0)} 条
- P0/P1事件：{'无' if not data.p0_p1_list else ''}
{_p0p1_as_md(data.p0_p1_list)}

## 五、平台分布
{_platform_as_md(data.platform_dist)}

## 六、处置状态统计
- 待跟进：{data.status_dist.get('待跟进', 0)} | 处理中：{data.status_dist.get('处理中', 0)} | 已处理：{data.status_dist.get('已处理', 0)} | 已放弃：{data.status_dist.get('已放弃', 0)} | 忽略：{data.status_dist.get('忽略', 0)}
"""


# ── Monthly report ─────────────────────────────────────────────────────
def generate_monthly(month_str: str = "") -> str:
    """Generate monthly report via IR pipeline (LLM → validate → render).

    v7.1: Uses engine.report_ir for structured generation with schema validation.
    Falls back to template on failure.
    统一报告源：生成后缓存 FinalReport（.report.json）。
    """
    if not month_str:
        month_str = datetime.now().strftime("%Y-%m")

    data = _collect_report_data(month_str=month_str)
    template = get_active_template("monthly")
    ir, markdown = _build_ir_and_markdown(data, template)

    try:
        from engine.report_ir import render_html
        html = render_html(ir)
    except Exception:
        html = ""

    fr = FinalReport(
        report_id=make_report_id("monthly", month_str),
        report_type="monthly",
        report_date=month_str,
        template_id=template.template_id,
        template_version=template.version,
        generated_at=datetime.now().isoformat(),
        status="published",
        data=asdict(data),
        ir=asdict(ir),
        markdown=markdown,
        html=html,
    )
    save_final_report(fr)

    return str(REPORTS_MONTHLY_DIR / f"{month_str}.md")


def _build_monthly_template(data: ReportData) -> str:
    """Built-in monthly template fallback (no LLM analysis)."""
    return f"""# 舆情月报 {data.date}

## 一、月度声量趋势
- 当月案例总数：{data.total_new_cases} 条

## 二、情感分布月度对比
- 正面：{_pct(data.sentiment_dist, '正面')}% | 中性：{_pct(data.sentiment_dist, '中性')}% | 负面：{_pct(data.sentiment_dist, '负面')}%

## 三、关键议题TOP5
{_list_as_md(data.top_issues)}

## 四、风险分级月度汇总
- P0：{data.severity_dist.get('P0', 0)} | P1：{data.severity_dist.get('P1', 0)} | P2：{data.severity_dist.get('P2', 0)} | P3：{data.severity_dist.get('P3', 0)}

## 五、平台分布
{_platform_as_md(data.platform_dist)}

## 六、处置状态统计
- 待跟进：{data.status_dist.get('待跟进', 0)} | 处理中：{data.status_dist.get('处理中', 0)} | 已处理：{data.status_dist.get('已处理', 0)} | 已放弃：{data.status_dist.get('已放弃', 0)} | 忽略：{data.status_dist.get('忽略', 0)}

## 七、处置效率统计
（待配置模板后自动生成）

## 八、下月监测建议
（待配置模板后自动生成）
"""


# ── HTML Report (v7.1 — IR-based) ──────────────────────────────────────

def generate_daily_html(data: ReportData) -> str:
    """Generate offline HTML report from IR. Returns path to HTML file."""
    from engine.report_ir import build_ir, render_html
    try:
        ir = build_ir(data, "daily")
        html = render_html(ir)
    except Exception:
        return ""
    REPORTS_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    html_path = REPORTS_DAILY_DIR / f"{data.date}.html"
    html_path.write_text(html, encoding="utf-8")
    return str(html_path)


def generate_monthly_html(data: ReportData) -> str:
    """Generate offline HTML monthly report from IR. Returns path to HTML file."""
    from engine.report_ir import build_ir, render_html
    try:
        ir = build_ir(data, "monthly")
        html = render_html(ir)
    except Exception:
        return ""
    REPORTS_MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    html_path = REPORTS_MONTHLY_DIR / f"{data.date}.html"
    html_path.write_text(html, encoding="utf-8")
    return str(html_path)


# ── Helpers ────────────────────────────────────────────────────────────
def _pct(dist: dict, key: str) -> int:
    total = sum(dist.values())
    if total == 0:
        return 0
    return round(dist.get(key, 0) / total * 100)


def _list_as_md(items: list[str]) -> str:
    if not items:
        return "（暂无数据）"
    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))


def _p0p1_as_md(items: list[dict]) -> str:
    if not items:
        return ""
    return "\n".join(f"- [{item.get('severity', '?')}] {item.get('title', '?')} ({item.get('platform', '?')}) — {item.get('status', '?')}" for item in items)


def _platform_as_md(dist: dict) -> str:
    if not dist:
        return "（暂无数据）"
    return "\n".join(f"- {k}：{v} 条" for k, v in dist.items())
