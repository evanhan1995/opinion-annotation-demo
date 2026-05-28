# -*- coding: utf-8 -*-
"""
舆情指挥系统 — 定时调度器

Schedules (PRD §7):
  日报: 每日 21:00
  月报: 每月 1 日 09:00
  Monitor 巡检: 每 6 小时 (00:00, 06:00, 12:00, 18:00)

Usage:
  python scheduler.py           # 启动调度器守护进程
  python scheduler.py --once    # 立即运行一次所有任务（测试用）
  python scheduler.py --daily   # 仅运行日报
  python scheduler.py --monitor # 仅运行 Monitor 巡检
"""
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Scheduler config persistence ──────────────────────────────────────
CONFIG_DIR = PROJECT_ROOT / "config"
SCHEDULER_CONFIG_PATH = CONFIG_DIR / "scheduler_config.json"

_SCHEDULER_CONFIG_DEFAULTS = {
    "version": 1,
    "auto_mode": False,
    "pipeline_frequency": "6h",
    "daily_report_time": "21:07",
    "monthly_report_time": "09:03",
    "monitor_times": ["00:07", "06:07", "12:07", "18:07"],
}


def load_scheduler_config() -> dict:
    """Load scheduler config from disk, merging with defaults."""
    if SCHEDULER_CONFIG_PATH.exists():
        try:
            data = json.loads(SCHEDULER_CONFIG_PATH.read_text(encoding="utf-8"))
            return {**_SCHEDULER_CONFIG_DEFAULTS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_SCHEDULER_CONFIG_DEFAULTS)


def save_scheduler_config(config: dict):
    """Save scheduler config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULER_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _parse_pipeline_hours(frequency: str) -> int:
    """Parse pipeline frequency string to hour interval. '2h'->2, '4h'->4, '6h'->6, '8h'->8."""

    if frequency.endswith("h"):
        try:
            return int(frequency[:-1])
        except ValueError:
            pass
    return 6


def run_daily_report():
    """Generate daily report via Orchestrator → Daily Report Agent."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 日报生成中...")
    try:
        from agents.orchestrator import run_daily_report as _run
        path = _run()
        print(f"  日报已保存: {path}")
    except Exception as e:
        print(f"  日报生成失败: {e}")


def run_monthly_report():
    """Generate monthly report (only on 1st of month)."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 月报生成中...")
    try:
        from agents.orchestrator import run_monthly_report as _run
        path = _run()
        print(f"  月报已保存: {path}")
    except Exception as e:
        print(f"  月报生成失败: {e}")


def run_monitor():
    """Execute keyword-based active monitoring."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Monitor 巡检中...")
    try:
        from agents.orchestrator import run_active_monitor
        result = run_active_monitor()
        if result.success:
            print(f"  巡检完成: {result.errors if result.errors else '无告警'}")
        else:
            print(f"  巡检异常: {result.errors}")
    except Exception as e:
        print(f"  Monitor 巡检失败: {e}")


def run_all():
    """Run all scheduled tasks once (for --once testing)."""
    print(f"=== 一次性调度执行 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    run_monitor()
    run_daily_report()
    run_monthly_report()
    print("=== 执行完毕 ===")


# ── Shared scheduler status (readable from Streamlit) ──────────────────
_scheduler_status: dict = {
    "running": False,
    "auto_mode": False,
    "last_daily": "",
    "last_monitor": "",
    "last_monthly": "",
    "last_pipeline": "",
    "next_daily": "21:07",
    "next_pipeline": "22:07",
    "next_monitor": "00:07 / 06:07 / 12:07 / 18:07",
    "errors": [],
}

# Persistence: write status to disk for cross-process visibility
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SCHEDULER_STATUS_PATH = OUTPUTS_DIR / "scheduler_status.json"
_last_status_write: float = 0


def _write_status_to_disk():
    global _last_status_write
    now = time.time()
    if now - _last_status_write < 30:
        return
    try:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        SCHEDULER_STATUS_PATH.write_text(
            json.dumps(_scheduler_status, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _last_status_write = now
    except OSError:
        pass


def _read_status_from_disk() -> dict:
    try:
        return json.loads(SCHEDULER_STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"running": False, "errors": []}


def get_scheduler_status() -> dict:
    """Return current scheduler status dict. Falls back to disk if thread is dead."""
    import copy
    if _scheduler_status.get("running"):
        return copy.deepcopy(_scheduler_status)
    return _read_status_from_disk()


def _register_jobs(sched_module, cfg: dict):
    """Register all scheduled jobs from config onto a schedule module instance."""
    sched_module.clear()

    sched_module.every().day.at(cfg["daily_report_time"]).do(_wrapped_run_daily)
    sched_module.every().day.at(cfg["monthly_report_time"]).do(_wrapped_monthly_guard)

    for t in cfg.get("monitor_times", []):
        sched_module.every().day.at(t).do(_wrapped_run_monitor)

    pipeline_freq = cfg.get("pipeline_frequency", "6h")
    pipeline_hours = _parse_pipeline_hours(pipeline_freq)
    sched_module.every(pipeline_hours).hours.do(_wrapped_run_pipeline)

    # Update status fields
    _scheduler_status["next_daily"] = cfg["daily_report_time"]
    _scheduler_status["next_pipeline"] = f"每 {pipeline_hours} 小时"
    _scheduler_status["next_monitor"] = " / ".join(cfg.get("monitor_times", []))
    _scheduler_status["auto_mode"] = cfg.get("auto_mode", False)
    _write_status_to_disk()


def start_scheduler():
    """Start the scheduling daemon."""
    import schedule as _schedule

    cfg = load_scheduler_config()
    _register_jobs(_schedule, cfg)

    _scheduler_status["running"] = True
    print(f"调度器已启动 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print(f"  日报: 每日 {cfg['daily_report_time']}")
    print(f"  月报: 每月 1 日 {cfg['monthly_report_time']}")
    print(f"  Monitor: {' / '.join(cfg['monitor_times'])}")
    print(f"  流水线: 每 {_parse_pipeline_hours(cfg.get('pipeline_frequency', '6h'))} 小时")
    print("  按 Ctrl+C 停止")

    _last_mtime = SCHEDULER_CONFIG_PATH.stat().st_mtime if SCHEDULER_CONFIG_PATH.exists() else 0

    while True:
        _schedule.run_pending()
        # Check for config changes every 60s
        try:
            cur_mtime = SCHEDULER_CONFIG_PATH.stat().st_mtime if SCHEDULER_CONFIG_PATH.exists() else 0
            if cur_mtime > _last_mtime:
                _last_mtime = cur_mtime
                new_cfg = load_scheduler_config()
                _register_jobs(_schedule, new_cfg)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 配置已更新, 作业已重新注册")
        except OSError:
            pass
        _write_status_to_disk()
        time.sleep(30)


# ── Streamlit-integrated background thread ──────────────────────────────
import threading


class SchedulerThread(threading.Thread):
    """Background thread that runs the scheduler loop.

    Reads schedule times from config/scheduler_config.json and
    auto-reloads when the file changes. Designed to run inside
    Streamlit via @st.cache_resource or as a standalone daemon.

    Usage in Streamlit:
        @st.cache_resource
        def get_scheduler():
            t = SchedulerThread()
            t.start()
            return t
    """

    _instance = None  # Singleton reference for alive checks

    def __init__(self):
        super().__init__(daemon=True, name="scheduler-thread")
        self._stop_event = threading.Event()
        SchedulerThread._instance = self

    def run(self):
        import schedule as _schedule

        cfg = load_scheduler_config()
        auto = cfg.get("auto_mode", False)
        if auto:
            _register_jobs(_schedule, cfg)

        _scheduler_status["running"] = True
        _last_mtime = SCHEDULER_CONFIG_PATH.stat().st_mtime if SCHEDULER_CONFIG_PATH.exists() else 0

        while not self._stop_event.is_set():
            _schedule.run_pending()
            # Check for config changes every 60s (the 30s sleep × 2 gives ~60s)
            try:
                cur_mtime = SCHEDULER_CONFIG_PATH.stat().st_mtime if SCHEDULER_CONFIG_PATH.exists() else 0
                if cur_mtime > _last_mtime:
                    _last_mtime = cur_mtime
                    new_cfg = load_scheduler_config()
                    new_auto = new_cfg.get("auto_mode", False)
                    if new_auto and not auto:
                        _register_jobs(_schedule, new_cfg)
                    elif not new_auto and auto:
                        _schedule.clear()
                        _scheduler_status["auto_mode"] = False
                    elif new_auto:
                        _register_jobs(_schedule, new_cfg)
                    auto = new_auto
            except OSError:
                pass
            _write_status_to_disk()
            time.sleep(30)

    def stop(self):
        _scheduler_status["running"] = False
        self._stop_event.set()


def _wrapped_run_daily():
    try:
        path = run_daily_report()
        _scheduler_status["last_daily"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        # Push daily report notification to Feishu
        try:
            from shared.notify import send_feishu_card
            from agents.curator import query_stats
            stats = query_stats()
            sev = stats.get("severity_dist", {})
            today = datetime.now().strftime("%Y-%m-%d")
            send_feishu_card(
                title=f"舆情日报 — {today}",
                body_text=(
                    f"**总案例**: {stats.get('total_cases', 0)} 条\n"
                    f"**P0**: {sev.get('P0', 0)}  **P1**: {sev.get('P1', 0)}  "
                    f"**P2**: {sev.get('P2', 0)}  **P3**: {sev.get('P3', 0)}"
                ),
                fields={
                    "平台数": str(stats.get("platform_count", 0)),
                    "P0/P1": f"{sev.get('P0', 0)}/{sev.get('P1', 0)}",
                },
                level="info",
            )
        except Exception:
            pass
    except Exception as e:
        _scheduler_status["errors"].append(f"日报失败: {e}")

def _wrapped_run_pipeline():
    try:
        from pipeline import trigger_pipeline
        trigger_pipeline(source="scheduler")
        _scheduler_status["last_pipeline"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    except Exception as e:
        _scheduler_status["errors"].append(f"流水线失败: {e}")

def _wrapped_run_monitor():
    try:
        run_monitor()
        _scheduler_status["last_monitor"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    except Exception as e:
        _scheduler_status["errors"].append(f"巡检失败: {e}")

def _wrapped_monthly_guard():
    if datetime.now().day == 1:
        try:
            path = run_monthly_report()
            _scheduler_status["last_monthly"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            _scheduler_status["errors"].append(f"月报失败: {e}")


def _monthly_guard():
    """Only run monthly report on the 1st day of month."""
    if datetime.now().day == 1:
        run_monthly_report()


def run_pipeline_cli() -> int:
    """Trigger pipeline and poll until completion. Returns exit code (0=success)."""
    from pipeline import trigger_pipeline, get_pipeline_status

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Triggering pipeline...")
    ok = trigger_pipeline(source="scheduler")
    if not ok:
        print("Error: Pipeline is already running or could not start")
        return 1

    while True:
        status = get_pipeline_status()
        if not status["is_running"]:
            break
        step = status.get("current_step", "?")
        for s in status.get("steps", []):
            if s["status"] == "running":
                pct = f" ({s.get('progress', 0)*100:.0f}%)" if s.get("progress") else ""
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] {s['label']}: {s['details']}{pct}")
        time.sleep(3)

    errors = status.get("errors", [])
    duration = status.get("total_duration_sec", 0)
    if errors:
        for e in errors[-5:]:
            print(f"  Error: {e}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Pipeline complete ({duration:.1f}s)")

    # Print step summary
    for s in status.get("steps", []):
        icon = {"done": "OK", "error": "FAIL", "pending": "SKIP"}.get(s["status"], s["status"])
        print(f"  {icon:4s} {s['label']}: {s.get('details', s['status'])}")

    return 1 if status.get("errors") else 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="舆情指挥系统定时调度器")
    parser.add_argument("--once", action="store_true", help="立即运行一次所有任务")
    parser.add_argument("--daily", action="store_true", help="仅运行日报")
    parser.add_argument("--monitor", action="store_true", help="仅运行 Monitor 巡检")
    parser.add_argument("--pipeline", action="store_true", help="触发完整流水线并等待完成")
    args = parser.parse_args()

    if args.once:
        run_all()
    elif args.daily:
        run_daily_report()
    elif args.monitor:
        run_monitor()
    elif args.pipeline:
        sys.exit(run_pipeline_cli())
    else:
        start_scheduler()
