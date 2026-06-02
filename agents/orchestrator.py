# -*- coding: utf-8 -*-
"""
舆情指挥系统 — Orchestrator
Pipeline coordinator and the ONLY component allowed to pass data between Agents.

Flows (PRD §3):
  流A: passive_analyze(url) → Scraper → Analyst → Handler → Curator
  流B: active_monitor() → Monitor → [for each] → 流A + P0/P1熔断
  流C: generate_daily_report() → Curator.query → DailyReport → output
  流D: answer_question(query) → Curator.search → answer

P0/P1熔断 (PRD §3.6):
  Analyst returns P0/P1 → Orchestrator immediately triggers emergency_dispatch()
  before the rest of the pipeline continues.
"""
import io
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# UTF-8 adapter
if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from agents.shared import (
    PROJECT_ROOT, OUTPUTS_DIR, RAW_DIR,
    RawData, Annotation, ActionPlan, KBEntry,
)


# ── Pipeline result ────────────────────────────────────────────────────
@dataclass
class PipelineResult:
    flow: str
    started_at: str
    finished_at: str
    success: bool
    annotation: Optional[Annotation] = None
    action_plan: Optional[ActionPlan] = None
    kb_entry: Optional[KBEntry] = None
    emergency_triggered: bool = False
    errors: list[str] = field(default_factory=list)
    item_results: list = field(default_factory=list)  # Flow B per-item PipelineResult objects


# ── Notification dispatch (PRD §3.6) ───────────────────────────────────
def _dispatch_emergency(annotation: Annotation) -> bool:
    """Deliver P0/P1 emergency alert via desktop popup + webhook."""
    triggered = False
    severity = annotation.severity
    title = annotation.summary[:60] if annotation.summary else "无标题"
    tags_str = ", ".join(annotation.risk_tags) if annotation.risk_tags else "无"
    msg_short = f"[{severity}] {title}"

    # Desktop alert
    if sys.platform == "win32":
        try:
            import subprocess
            ps_script = (
                f'Add-Type -AssemblyName System.Windows.Forms;'
                f'Add-Type -AssemblyName System.Media;'
                f'[System.Media.SystemSounds]::Hand.Play();'
                f'[System.Windows.Forms.MessageBox]::Show('
                f'\'{msg_short}\\n\\n平台: {annotation.platform}\\n风险: {tags_str}\\n\\n{annotation.url}\','
                f'\'舆情{severity}告警\','
                f'[System.Windows.Forms.MessageBoxButtons]::OK,'
                f'[System.Windows.Forms.MessageBoxIcon]::Warning)'
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            triggered = True
        except Exception:
            pass

    # Webhook dispatch
    notif_config_path = PROJECT_ROOT / "notification_config.json"
    if notif_config_path.exists():
        try:
            cfg = json.loads(notif_config_path.read_text(encoding="utf-8"))
            for wh in cfg.get("webhooks", []):
                if not wh.get("enabled"):
                    continue
                levels = wh.get("trigger_level", "P0")
                if severity in levels.replace("+", " ").split() if "P0+P1" in levels else [severity]:
                    # Allow P0+P1 format
                    pass
                if ("P0" in levels and severity == "P0") or ("P1" in levels and severity == "P1"):
                    _send_webhook(wh["url"], annotation)
                    triggered = True
        except Exception:
            pass

    return triggered


def _send_webhook(url: str, annotation: Annotation):
    """Send emergency alert to Feishu/WeCom webhook."""
    try:
        import requests
        title = annotation.summary[:100] if annotation.summary else "无标题"
        tags_str = ", ".join(annotation.risk_tags) if annotation.risk_tags else "无"

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"舆情{annotation.severity}告警"},
                    "template": "red" if annotation.severity == "P0" else "yellow",
                },
                "elements": [
                    {"tag": "markdown", "content": f"**{title}**"},
                    {"tag": "markdown",
                     "content": f"平台: {annotation.platform} | 风险: {tags_str}"},
                    {"tag": "markdown",
                     "content": f"分流建议: {annotation.triage}"},
                    {"tag": "markdown", "content": f"[查看原文]({annotation.url})"},
                ],
            },
        }
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass


# ── Scraper degradation tracking (PRD S-06) ────────────────────────────
import threading as _threading
_SCRAPER_FAILURES: dict[str, int] = {}  # platform → consecutive failure count
_failures_lock = _threading.Lock()


def get_scraper_degraded() -> tuple[bool, str]:
    """Check if any platform has 3+ consecutive scraper failures.

    Returns (is_degraded, platform_name). UI checks this to show manual feed.
    """
    with _failures_lock:
        for pf, count in _SCRAPER_FAILURES.items():
            if count >= 3:
                return True, pf
    return False, ""


def reset_scraper_failures(platform: str = ""):
    """Reset failure counter (called after successful fetch or manual feed)."""
    with _failures_lock:
        if platform:
            _SCRAPER_FAILURES.pop(platform, None)
        else:
            _SCRAPER_FAILURES.clear()


# ── Data clipping (PRD §3.4) — Channel isolation by field selection.
# Agent interfaces already enforce this via typed dataclasses (RawData → Annotation → ActionPlan → KBEntry);
# additional field-level clipping proved unnecessary in practice.


# ── Flow A: Passive analysis ──────────────────────────────────────────
def run_passive_analysis(url: str, pipeline_notes: str = "",
                         progress_callback=None,
                         init_status: str = "待跟进") -> PipelineResult:
    """User submits a URL → full pipeline: Scraper → Analyst → Handler → Curator.

    Args:
        progress_callback: Optional callable(stage: str, details: str) for
            sub-step progress reporting (e.g. pipeline UI).
    """
    started = datetime.now().isoformat()
    errors = []

    # ── Stage 1: Scrape ───────────────────────────────────────────────
    if progress_callback:
        progress_callback("scrape", f"抓取: {url[:60]}...")
    try:
        from agents.scraper import fetch, detect_platform
        raw = fetch(url)
        platform = detect_platform(url)
        if raw.comments_raw and any("error" in str(c).lower() or "fail" in str(c).lower() or "unsupported" in str(c).lower() for c in raw.comments_raw):
            with _failures_lock:
                _SCRAPER_FAILURES[platform] = _SCRAPER_FAILURES.get(platform, 0) + 1
        elif not raw.content and not raw.title:
            with _failures_lock:
                _SCRAPER_FAILURES[platform] = _SCRAPER_FAILURES.get(platform, 0) + 1
        else:
            with _failures_lock:
                _SCRAPER_FAILURES.pop(platform, None)  # Reset on success
    except Exception as e:
        platform = detect_platform(url) if 'detect_platform' in dir() else url
        if isinstance(platform, str) and platform != url:
            with _failures_lock:
                _SCRAPER_FAILURES[platform] = _SCRAPER_FAILURES.get(platform, 0) + 1
        return PipelineResult(
            flow="passive_analysis", started_at=started,
            finished_at=datetime.now().isoformat(), success=False,
            errors=[f"[{platform}] Scraper error for {url}: {e}"],
        )

    if not raw.content and not raw.title:
        # Check comments_raw for error details to enrich the message
        error_hint = ""
        if raw.comments_raw:
            err_parts = [c for c in raw.comments_raw if "error" in str(c).lower() or "fail" in str(c).lower()]
            if err_parts:
                error_hint = f" [{err_parts[0][:100]}]"
        return PipelineResult(
            flow="passive_analysis", started_at=started,
            finished_at=datetime.now().isoformat(), success=False,
            errors=[f"[{platform}] Fetch returned empty content for {url}{error_hint}"],
        )

    # ── Stage 2: Sentinel pre-filter (v6.0) ─────────────────────────────
    if progress_callback:
        progress_callback("sentinel", "预筛选...")
    try:
        from agents.sentinel import screen_content
        sentinel_result = screen_content(raw.content, raw.platform)
    except Exception:
        sentinel_result = None  # Degrade gracefully if sentinel fails

    # Reject — skip entire pipeline
    if sentinel_result and sentinel_result.verdict == "reject":
        return PipelineResult(
            flow="passive_analysis", started_at=started,
            finished_at=datetime.now().isoformat(), success=True,
            errors=[f"[{raw.platform}] Sentinel rejected: {sentinel_result.reason}"],
        )

    # ── Stage 3: Analyst ──────────────────────────────────────────────
    if progress_callback:
        progress_callback("annotate", "LLM标注中..." if not (
            sentinel_result and sentinel_result.verdict == "fast_track"
        ) else "快速通道标注中...")
    try:
        from agents.analyst import annotate
        if sentinel_result and sentinel_result.verdict == "fast_track":
            annotation = annotate(raw, use_llm=False, sentinel_result=sentinel_result)
        else:
            annotation = annotate(raw)
    except Exception as e:
        return PipelineResult(
            flow="passive_analysis", started_at=started,
            finished_at=datetime.now().isoformat(), success=False,
            errors=[f"[{raw.platform}] Analyst error for {url}: {e}"],
        )

    # P0/P1 meltdown
    emergency = False
    if annotation.severity in ("P0", "P1"):
        emergency = emergency_dispatch(annotation)

    # ── Stage 3: Handler ──────────────────────────────────────────────
    if progress_callback:
        progress_callback("handler", "生成处置方案...")
    try:
        from agents.handler import triage
        action_plan = triage(annotation)
    except Exception as e:
        errors.append(f"Handler error: {e}")
        action_plan = None

    # ── Stage 4: Curator ──────────────────────────────────────────────
    if progress_callback:
        progress_callback("ingest", "案例入库...")
    try:
        from agents.curator import ingest
        kb_entry = ingest(raw, annotation, notes=pipeline_notes,
                          init_status=init_status)
    except Exception as e:
        errors.append(f"Curator error: {e}")
        kb_entry = None

    return PipelineResult(
        flow="passive_analysis",
        started_at=started,
        finished_at=datetime.now().isoformat(),
        success=len(errors) == 0,
        annotation=annotation,
        action_plan=action_plan,
        kb_entry=kb_entry,
        emergency_triggered=emergency,
        errors=errors,
    )


# ── Flow B: Active monitoring ─────────────────────────────────────────
def run_active_monitor(pipeline_notes: str = "",
                       date_from: str = "", date_to: str = "") -> PipelineResult:
    """Scheduled keyword search -> batch pipeline: Monitor -> [for each] -> Flow A.

    Args:
        date_from: YYYY-MM-DD, passed through to execute_job for date-range mode.
        date_to: YYYY-MM-DD, passed through to execute_job for date-range mode.
    """
    started = datetime.now().isoformat()
    errors = []

    try:
        from agents.monitor import execute_job
        harvest = execute_job(date_from=date_from, date_to=date_to)
    except Exception as e:
        return PipelineResult(
            flow="active_monitor", started_at=started,
            finished_at=datetime.now().isoformat(), success=False,
            errors=[f"Monitor error: {e}"],
        )

    # For each new item, run passive analysis
    item_results = []
    for kr in harvest.keyword_results:
        for item in kr.new_items:
            try:
                result = run_passive_analysis(item.url, pipeline_notes=pipeline_notes)
                item_results.append(result)
                if result.emergency_triggered:
                    errors.append(f"P0/P1 meltdown triggered: {item.url}")
                if not result.success:
                    errors.extend(result.errors)
            except Exception as e:
                errors.append(f"Item pipeline error ({item.url}): {e}")

    return PipelineResult(
        flow="active_monitor",
        started_at=started,
        finished_at=datetime.now().isoformat(),
        success=len(errors) == 0,
        errors=errors if errors else [],
        item_results=item_results,
    )


# ── Flow C: Daily report generation ────────────────────────────────────
def run_daily_report(date_str: str = "") -> str:
    """Generate daily report via Daily Report Agent. Returns path to report file."""
    try:
        from agents.daily_report import generate_daily
        return generate_daily(date_str)
    except Exception as e:
        return f"日报生成失败: {e}"


def run_monthly_report(month_str: str = "") -> str:
    """Generate monthly report via Daily Report Agent. Returns path to report file."""
    try:
        from agents.daily_report import generate_monthly
        return generate_monthly(month_str)
    except Exception as e:
        return f"月报生成失败: {e}"


# ── Flow D: Knowledge base Q&A ────────────────────────────────────────
def answer_question(query: str) -> str:
    """Query the knowledge base via Curator Agent."""
    try:
        from agents.curator import answer_query
        return answer_query(query)
    except Exception as e:
        return f"知识库问答出错: {e}"


# ── Handler → Curator status sync ──────────────────────────────────────
def handle_status_transition(case_id: str, from_status: str, to_status: str,
                              notes: str = "", operator: str = "系统") -> dict:
    """Handler validates → Orchestrator proxies → Curator updates KB + timeline.

    PRD §3.5 channel 2: the only legal path for Handler→Curator communication.
    PRD H-04: records disposition timeline (time + operator + notes) for each change.
    """
    from agents.handler import validate_transition
    if not validate_transition(from_status, to_status):
        return {"success": False, "error": f"Invalid transition: {from_status} → {to_status}"}

    from agents.curator import update_case_status
    result = update_case_status(case_id, to_status, notes)

    # Append disposition timeline to case file
    if result.get("success"):
        _log_disposition_timeline(case_id, from_status, to_status, notes, operator)

    # Auto-escalation hint for P0/P1 when moving to 处理中
    if to_status == "处理中" and from_status == "待跟进":
        result["escalation_hint"] = "考虑是否需要上升至PR部或法务部协同处理"

    return result


def _log_disposition_timeline(case_id: str, from_status: str, to_status: str,
                               notes: str, operator: str):
    """Record disposition timeline entry via Curator (PRD: single legal path)."""
    from agents.curator import append_timeline
    append_timeline(case_id, from_status, to_status, notes, operator)


# ── Emergency dispatch (called inline during pipeline) ─────────────────
def emergency_dispatch(annotation: Annotation) -> bool:
    """PRD §3.6: P0/P1 immediate alert. Call from pipeline when severity in {P0, P1}."""
    return _dispatch_emergency(annotation)
