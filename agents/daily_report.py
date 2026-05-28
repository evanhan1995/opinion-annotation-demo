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
import io
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agents.shared import (
    get_llm, load_prompt, PROJECT_ROOT, WIKI_DIR,
)

DAILY_REPORT_PROMPT = ""


def _get_prompt() -> str:
    global DAILY_REPORT_PROMPT
    if not DAILY_REPORT_PROMPT:
        DAILY_REPORT_PROMPT = load_prompt("daily_report_system")
    return DAILY_REPORT_PROMPT


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

    data.monitor_stats = {"搜索关键词数": 0, "去重率": 0}

    return data


# ── Daily report ───────────────────────────────────────────────────────
def generate_daily(date_str: str = "") -> str:
    """Generate daily report from real case metrics. Returns path to report file.

    Phase 3: LLM generation via DeepSeek with template fallback.
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    data = _collect_report_data(date_str)
    content = _build_daily_markdown(data)

    REPORTS_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DAILY_DIR / f"{date_str}.md"
    report_path.write_text(content, encoding="utf-8")
    return str(report_path)


_TEMPLATES_DIR = PROJECT_ROOT / "templates"


def _read_template(filename: str) -> str | None:
    """Read a template file if it exists."""
    path = _TEMPLATES_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _build_daily_markdown(data: ReportData) -> str:
    """Build daily report via LLM (DeepSeek).

    1. If templates/daily_report_template.md exists → use it as format guide
    2. If LLM fails → fallback to built-in template
    """
    template = _read_template("daily_report_template.md")

    try:
        client, model = get_llm("deepseek")
    except Exception:
        return _build_daily_template(data)

    p0p1_str = ""
    for item in data.p0_p1_list:
        p0p1_str += f"- [{item.get('severity', '?')}] {item.get('title', '?')} ({item.get('platform', '?')})\n"

    platform_str = "\n".join(f"- {k}：{v} 条" for k, v in data.platform_dist.items()) if data.platform_dist else "暂无"

    if template:
        prompt = f"""根据以下舆情统计数据，严格按照提供的模板格式生成一份舆情日报。

**模板格式**（必须严格遵循此结构）：
```
{template}
```

**实际数据**：
- 日期：{data.date}
- 案例总数：{data.total_new_cases} 条（前7日均值：{data.avg_prev_7days} 条）
- 情感分布：正面 {_pct(data.sentiment_dist, '正面')}% / 中性 {_pct(data.sentiment_dist, '中性')}% / 负面 {_pct(data.sentiment_dist, '负面')}%
- 关键议题：{', '.join(data.top_issues) if data.top_issues else '无'}
- 严重度分布：P0={data.severity_dist.get('P0',0)}, P1={data.severity_dist.get('P1',0)}, P2={data.severity_dist.get('P2',0)}, P3={data.severity_dist.get('P3',0)}
- 平台分布：{platform_str}
- 处置状态：待跟进={data.status_dist.get('待跟进',0)}, 处理中={data.status_dist.get('处理中',0)}, 已处理={data.status_dist.get('已处理',0)}, 已放弃={data.status_dist.get('已放弃',0)}, 忽略={data.status_dist.get('忽略',0)}
- P0/P1事件：\n{p0p1_str or '无'}

要求：
1. 将数据填入模板中，替换 {{{{占位符}}}}
2. 保持模板的章节结构不变
3. 每个章节简洁专业（2-4句），突出异常和趋势
4. 只输出 Markdown，不要额外解释"""
    else:
        prompt = f"""根据以下舆情统计数据，生成一份专业的舆情日报（Markdown 格式）。

日期：{data.date}
案例总数：{data.total_new_cases} 条（前7日均值：{data.avg_prev_7days} 条）
情感分布：正面 {_pct(data.sentiment_dist, '正面')}% / 中性 {_pct(data.sentiment_dist, '中性')}% / 负面 {_pct(data.sentiment_dist, '负面')}%
关键议题：{', '.join(data.top_issues) if data.top_issues else '无'}
严重度分布：P0={data.severity_dist.get('P0',0)}, P1={data.severity_dist.get('P1',0)}, P2={data.severity_dist.get('P2',0)}, P3={data.severity_dist.get('P3',0)}
平台分布：{platform_str}
处置状态：待跟进={data.status_dist.get('待跟进',0)}, 处理中={data.status_dist.get('处理中',0)}, 已处理={data.status_dist.get('已处理',0)}, 已放弃={data.status_dist.get('已放弃',0)}, 忽略={data.status_dist.get('忽略',0)}
P0/P1事件：
{p0p1_str or '无'}

要求：
1. 标题为"# 舆情日报 {data.date}"
2. 包含6个章节：一、声量概览 / 二、情感分布 / 三、关键议题 / 四、风险分级 / 五、平台分布 / 六、处置状态统计
3. 每个章节简洁专业（2-4句），突出异常和趋势
4. P0/P1事件需要单独列出
5. 只输出 Markdown，不要额外解释"""

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=2048,
            temperature=0.4,
            timeout=60,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        if content and content.startswith("#"):
            return content
    except Exception:
        pass

    return _build_daily_template(data)


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
    """Generate monthly report from real case metrics.

    1. If templates/monthly_report_template.md exists → LLM fills template
    2. Fallback to built-in template
    """
    if not month_str:
        month_str = datetime.now().strftime("%Y-%m")

    data = _collect_report_data(month_str=month_str)
    template = _read_template("monthly_report_template.md")

    if template:
        try:
            client, model = get_llm("deepseek")
            platform_str = "\n".join(f"- {k}：{v} 条" for k, v in data.platform_dist.items()) if data.platform_dist else "暂无"
            prompt = f"""根据以下舆情统计数据，严格按照提供的模板格式生成一份舆情月报。

**模板格式**（必须严格遵循此结构）：
```
{template}
```

**实际数据**：
- 月份：{month_str}
- 案例总数：{data.total_new_cases} 条
- 情感分布：正面 {_pct(data.sentiment_dist, '正面')}% / 中性 {_pct(data.sentiment_dist, '中性')}% / 负面 {_pct(data.sentiment_dist, '负面')}%
- 关键议题：{', '.join(data.top_issues) if data.top_issues else '无'}
- 严重度分布：P0={data.severity_dist.get('P0',0)}, P1={data.severity_dist.get('P1',0)}, P2={data.severity_dist.get('P2',0)}, P3={data.severity_dist.get('P3',0)}
- 平台分布：{platform_str}
- 处置状态：待跟进={data.status_dist.get('待跟进',0)}, 处理中={data.status_dist.get('处理中',0)}, 已处理={data.status_dist.get('已处理',0)}, 已放弃={data.status_dist.get('已放弃',0)}, 忽略={data.status_dist.get('忽略',0)}

要求：将数据填入模板替换{{{{占位符}}}}，保持模板结构，只输出Markdown。"""

            response = client.chat.completions.create(
                model=model, max_tokens=2048, temperature=0.4, timeout=60,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            if content and content.startswith("#"):
                REPORTS_MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
                report_path = REPORTS_MONTHLY_DIR / f"{month_str}.md"
                report_path.write_text(content, encoding="utf-8")
                return str(report_path)
        except Exception:
            pass

    # Fallback: built-in template
    content = f"""# 舆情月报 {month_str}

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
    REPORTS_MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_MONTHLY_DIR / f"{month_str}.md"
    report_path.write_text(content, encoding="utf-8")
    return str(report_path)


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
