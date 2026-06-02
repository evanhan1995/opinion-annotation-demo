# -*- coding: utf-8 -*-
"""Automation pipeline: Monitor -> Annotate -> Ingest -> Disposition -> Daily Report.

5-step sequential pipeline with thread-safe status tracking for sidebar UI.
Runs in a daemon thread so it never blocks the Streamlit main thread.
"""

import threading
import time
from concurrent import futures
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StepStatus:
    name: str = ""
    label: str = ""
    status: str = "pending"  # pending | running | done | error
    details: str = ""
    progress: float = 0.0
    error: str = ""


@dataclass
class PipelineStatus:
    is_running: bool = False
    is_auto_mode: bool = False
    triggered_by: str = ""
    started_at: str = ""
    finished_at: str = ""
    current_step: str = ""
    init_status: str = "待跟进"
    sort_preference: str = "default"
    steps: list = field(default_factory=lambda: [
        StepStatus(name="monitor", label="Monitor抓取"),
        StepStatus(name="annotate", label="AI标注"),
        StepStatus(name="ingest", label="入库"),
        StepStatus(name="disposition", label="案例处置"),
        StepStatus(name="daily_report", label="生成日报"),
    ])
    errors: list = field(default_factory=list)
    total_duration_sec: float = 0.0


_PIPELINE_TIMEOUT_SEC = 1800  # 30 min overall pipeline hard cap

_pipeline_status = PipelineStatus()
_pipeline_harvest = None
_lock = threading.Lock()


def get_pipeline_status() -> dict:
    """Thread-safe read of current pipeline status."""
    with _lock:
        steps = []
        for s in _pipeline_status.steps:
            steps.append({
                "name": s.name, "label": s.label, "status": s.status,
                "details": s.details, "progress": s.progress, "error": s.error,
            })
        return {
            "is_running": _pipeline_status.is_running,
            "is_auto_mode": _pipeline_status.is_auto_mode,
            "triggered_by": _pipeline_status.triggered_by,
            "init_status": _pipeline_status.init_status,
            "sort_preference": _pipeline_status.sort_preference,
            "started_at": _pipeline_status.started_at,
            "finished_at": _pipeline_status.finished_at,
            "current_step": _pipeline_status.current_step,
            "steps": steps,
            "errors": _pipeline_status.errors,
            "total_duration_sec": _pipeline_status.total_duration_sec,
        }


def trigger_pipeline(source: str = "manual", init_status: str = "待跟进",
                     sort_preference: str = "default") -> bool:
    """Kick off a full pipeline run in a background daemon thread."""
    with _lock:
        if _pipeline_status.is_running:
            return False
        _reset_status()
        _pipeline_status.is_running = True
        _pipeline_status.triggered_by = source
        _pipeline_status.init_status = init_status
        _pipeline_status.sort_preference = sort_preference
        _pipeline_status.started_at = datetime.now().isoformat()

    t = threading.Thread(target=_run_pipeline, daemon=True, name="pipeline-thread")
    t.start()
    return True


def set_auto_mode(enabled: bool):
    with _lock:
        _pipeline_status.is_auto_mode = enabled


def reset_pipeline():
    with _lock:
        _pipeline_status = PipelineStatus()


def force_reset_pipeline() -> bool:
    """Force-reset a stuck pipeline. Returns True if a reset was needed."""
    global _pipeline_status
    with _lock:
        was_running = _pipeline_status.is_running
        if was_running:
            _pipeline_status = PipelineStatus()
            _pipeline_status.errors.append("流水线被强制重置（超时或手动干预）")
        return was_running


def _reset_status():
    _pipeline_status.is_running = False
    _pipeline_status.finished_at = ""
    _pipeline_status.current_step = ""
    _pipeline_status.errors = []
    _pipeline_status.total_duration_sec = 0.0
    for s in _pipeline_status.steps:
        s.status = "pending"
        s.details = ""
        s.progress = 0.0
        s.error = ""


def _update_step(name: str, status: str, details: str = "", progress: float = 0.0, error: str = ""):
    with _lock:
        for step in _pipeline_status.steps:
            if step.name == name:
                step.status = status
                if details:
                    step.details = details
                step.progress = progress
                if error:
                    step.error = error
                if status == "running":
                    _pipeline_status.current_step = name


def _check_timeout(start_time: float) -> bool:
    """Return True if overall pipeline timeout exceeded."""
    return (time.time() - start_time) > _PIPELINE_TIMEOUT_SEC


def _run_pipeline():
    """Execute pipeline steps sequentially in background thread.

    Step 1 does monitor search once. Step 2 iterates over the NEW items
    (no re-search).  Steps 3-5 verify, escalate, and report.
    """
    start_time = time.time()
    init_status = _pipeline_status.init_status
    sort_pref = _pipeline_status.sort_preference
    severity_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}

    # Read last patrol time for date-range mode (same as scheduler)
    import json as _json
    last_path = PROJECT_ROOT / "config" / "last_patrol.json"
    date_from = ""
    date_to = datetime.now().strftime("%Y-%m-%d")
    if last_path.exists():
        try:
            data = _json.loads(last_path.read_text(encoding="utf-8"))
            date_from = data.get("last_patrol_date", "")
        except Exception:
            pass

    try:
        # Step 1: Monitor — search once, store harvest globally
        _update_step("monitor", "running", details="正在执行关键词巡检...")
        try:
            from agents.monitor import execute_job

            def _monitor_progress(details: str):
                _update_step("monitor", "running", details=details)

            # Wrap execute_job in a hard timeout — yt-dlp can hang indefinitely
            # in daemon threads even with socket_timeout set.
            _MONITOR_HARD_TIMEOUT = 120
            _exec = futures.ThreadPoolExecutor(max_workers=1)
            try:
                _fut = _exec.submit(execute_job, progress_callback=_monitor_progress,
                                    sort_preference=sort_pref,
                                    date_from=date_from, date_to=date_to)
                harvest = _fut.result(timeout=_MONITOR_HARD_TIMEOUT)
            except futures.TimeoutError:
                _update_step("monitor", "error", error="Monitor搜索超时(120s)，跳过")
                return
            finally:
                _exec.shutdown(wait=False)
            if _check_timeout(start_time):
                _update_step("monitor", "error", error="流水线整体超时")
                return
            # Store harvest so step 2 can access it (don't re-search)
            global _pipeline_harvest
            _pipeline_harvest = harvest
            _update_step("monitor", "done",
                         details=f"获取{harvest.total_fetched}条, 新增{harvest.total_new}条",
                         progress=1.0)
        except Exception as e:
            _update_step("monitor", "error", error=str(e))
            return

        # Step 2: AI annotation — process each NEW item (harvest from step 1)
        new_items = []
        for kr in harvest.keyword_results:
            for item in kr.new_items:
                new_items.append(item)
        total_items = len(new_items)

        if total_items == 0:
            _update_step("annotate", "done", details="无新增内容，跳过标注", progress=1.0)
        else:
            _update_step("annotate", "running",
                         details=f"0/{total_items}", progress=0.0)
            from agents.orchestrator import run_passive_analysis

            errors = []
            completed_count = 0
            _ITEM_TIMEOUT = 300  # 5 min per item hard cap

            def _process_one(item):
                try:
                    executor = futures.ThreadPoolExecutor(max_workers=1)
                    try:
                        fut = executor.submit(
                            run_passive_analysis,
                            item.url, "自动化处置", None,
                            init_status=init_status,
                        )
                        try:
                            result = fut.result(timeout=_ITEM_TIMEOUT)
                        except futures.TimeoutError:
                            return [f"Item timeout ({item.url}): {_ITEM_TIMEOUT}s"], "P3"
                    finally:
                        executor.shutdown(wait=False)
                    sev = result.annotation.severity if result.annotation else "P3"
                    if not result.success:
                        return result.errors, sev
                    return [], sev
                except Exception as e:
                    return [f"Item pipeline error ({item.url}): {e}"], "P3"

            with futures.ThreadPoolExecutor(max_workers=3) as pool:
                future_to_item = {pool.submit(_process_one, item): item for item in new_items}
                for fut in futures.as_completed(future_to_item):
                    item_errors, sev = fut.result()
                    if sev in severity_counts:
                        severity_counts[sev] += 1
                    if item_errors:
                        errors.extend(item_errors)
                    completed_count += 1
                    _update_step("annotate", "running",
                                 details=f"{completed_count}/{total_items}",
                                 progress=completed_count / total_items)

            if errors:
                with _lock:
                    _pipeline_status.errors.extend(errors)
            _update_step("annotate", "done",
                         details=f"标注完成 {total_items}条" +
                         (f" ({len(errors)}条告警)" if errors else ""),
                         progress=1.0)

        if _check_timeout(start_time):
            _update_step("ingest", "error", error="流水线超时，后续步骤跳过")
            _update_step("disposition", "error", error="流水线超时，后续步骤跳过")
            _update_step("daily_report", "error", error="流水线超时，后续步骤跳过")
            return

        # Step 3: Ingest verification (already happened inside run_passive_analysis)
        _update_step("ingest", "running", details="验证案例入库...")
        try:
            from agents.curator import query_stats
            stats = query_stats()
            _update_step("ingest", "done",
                         details=f"知识库共{stats['total_cases']}条案例",
                         progress=1.0)
        except Exception as e:
            _update_step("ingest", "error", error=str(e))

        # Step 4: Case disposition (auto-escalate P0/P1 via Orchestrator)
        _update_step("disposition", "running", details="检查高优案例状态...")
        try:
            from agents.curator import query_cases
            from agents.orchestrator import handle_status_transition
            p0p1 = query_cases({"severity": ["P0", "P1"], "status": "待跟进"})
            p0p1 = [c for c in p0p1 if c.get("severity") in ("P0", "P1")]
            escalated = 0
            for c in p0p1:
                try:
                    result = handle_status_transition(
                        c["case_id"], "待跟进", "处理中",
                        notes="流水线自动升级: P0/P1高优案例",
                        operator="流水线",
                    )
                    if result.get("success"):
                        escalated += 1
                except Exception:
                    pass
            _update_step("disposition", "done",
                         details=f"已升级{escalated}条高优案例" if escalated else "无待处理高优案例",
                         progress=1.0)
        except Exception as e:
            _update_step("disposition", "error", error=str(e))

        # Step 5: Daily report
        _update_step("daily_report", "running", details="正在生成日报...")
        try:
            from agents.orchestrator import run_daily_report
            path = run_daily_report()
            _update_step("daily_report", "done",
                         details=f"日报已保存" if path else "日报已生成",
                         progress=1.0)
        except Exception as e:
            _update_step("daily_report", "error", error=str(e))
        # ── Pipeline completion notification ──
        _notify_pipeline_complete(harvest, severity_counts)

    finally:
        _finalize(start_time)


def _notify_pipeline_complete(harvest, severity_counts: dict):
    """Send pipeline completion summary to Feishu bot."""
    try:
        from shared.notify import send_feishu_card
    except ImportError:
        return

    # Collect keywords
    keywords = []
    for kr in harvest.keyword_results:
        if kr.keyword not in keywords:
            keywords.append(kr.keyword)
    kw_str = "、".join(keywords) if keywords else "N/A"

    # Step statuses
    step_lines = []
    with _lock:
        for step in _pipeline_status.steps:
            icon_map = {"done": "✅", "error": "❌", "pending": "⏭️"}
            icon = icon_map.get(step.status, "⏳")
            detail = step.details if step.details else step.status
            step_lines.append(f"{icon} {step.label}: {detail}")

    # Determine level
    if severity_counts.get("P0", 0) > 0:
        level = "error"
    elif severity_counts.get("P1", 0) > 0:
        level = "warning"
    else:
        level = "success"

    body = (
        f"**关键词**: {kw_str}\n"
        f"**抓取总数**: {harvest.total_fetched} 条\n"
        f"**新增入库**: {harvest.total_new} 条\n"
        "\n" + "\n".join(step_lines)
    )

    send_feishu_card(
        title=f"舆情巡检完成 — {kw_str}",
        body_text=body,
        fields={
            "P0": str(severity_counts.get("P0", 0)),
            "P1": str(severity_counts.get("P1", 0)),
            "P2": str(severity_counts.get("P2", 0)),
            "P3": str(severity_counts.get("P3", 0)),
        },
        level=level,
    )


def _finalize(start_time: float):
    with _lock:
        _pipeline_status.is_running = False
        _pipeline_status.finished_at = datetime.now().isoformat()
        _pipeline_status.total_duration_sec = time.time() - start_time
        _pipeline_status.current_step = ""
