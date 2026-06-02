# -*- coding: utf-8 -*-
"""High-risk tracking engine — data model, CRUD, scrape-and-record, delta compute.

Data layout:
  config/tracking_cases.json     → case registry (list of case dicts)
  outputs/tracking/{id}_history.json → per-case time-series snapshots
"""

import io
import json
import sys
import time as _time_module
from datetime import datetime
from pathlib import Path

import engine._compat

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TRACKING_CONFIG_PATH = CONFIG_DIR / "tracking_cases.json"
TRACKING_DATA_DIR = OUTPUTS_DIR / "tracking"

_METRIC_MAP = {
    "views": "播放量",
    "likes": "点赞",
    "comments": "评论",
    "shares": "收藏",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Config CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def load_tracking_cases() -> list[dict]:
    """Load all tracking cases from config. Returns list of case dicts."""
    if TRACKING_CONFIG_PATH.exists():
        try:
            data = json.loads(TRACKING_CONFIG_PATH.read_text(encoding="utf-8"))
            return data.get("cases", [])
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_tracking_cases(cases: list[dict]):
    """Persist tracking case list to config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TRACKING_CONFIG_PATH.write_text(
        json.dumps({"version": 1, "cases": cases}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_case_by_id(case_id: str) -> dict | None:
    """Find a tracking case by ID. Returns None if not found."""
    for c in load_tracking_cases():
        if c.get("id") == case_id:
            return c
    return None


def get_all_enabled_cases() -> list[dict]:
    """Return all tracking cases with enabled=True."""
    return [c for c in load_tracking_cases() if c.get("enabled", True)]


# ═══════════════════════════════════════════════════════════════════════════════
# Case lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

def add_tracking_case(url: str, label: str = "", interval_minutes: int = 120,
                      alerts: list[dict] | None = None) -> str:
    """Add a new tracking case. Returns the new case_id."""
    cases = load_tracking_cases()

    # Generate sequential ID
    existing_ids = [c.get("id", "") for c in cases]
    next_num = 1
    while f"track-{next_num:03d}" in existing_ids:
        next_num += 1
    case_id = f"track-{next_num:03d}"

    # Detect platform
    from engine.scraper import _detect_platform
    platform = _detect_platform(url)

    case = {
        "id": case_id,
        "url": url,
        "label": label or url[:60],
        "platform": platform,
        "interval_minutes": interval_minutes,
        "alerts": alerts or [],
        "enabled": True,
        "created_at": datetime.now().isoformat(),
    }
    cases.append(case)
    save_tracking_cases(cases)
    return case_id


def remove_tracking_case(case_id: str):
    """Delete a tracking case and its history file."""
    cases = [c for c in load_tracking_cases() if c.get("id") != case_id]
    save_tracking_cases(cases)
    # Remove history file
    history_path = _history_path(case_id)
    if history_path.exists():
        history_path.unlink()


def update_tracking_case(case_id: str, updates: dict):
    """Update fields of an existing tracking case."""
    cases = load_tracking_cases()
    for c in cases:
        if c.get("id") == case_id:
            c.update(updates)
            break
    save_tracking_cases(cases)


# ═══════════════════════════════════════════════════════════════════════════════
# History storage
# ═══════════════════════════════════════════════════════════════════════════════

def _history_path(case_id: str) -> Path:
    """Get the path to a case's history JSON file."""
    return TRACKING_DATA_DIR / f"{case_id}_history.json"


def get_case_history(case_id: str) -> list[dict]:
    """Read time-series history for a tracking case."""
    hp = _history_path(case_id)
    if hp.exists():
        try:
            return json.loads(hp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _append_history(case_id: str, record: dict):
    """Append a new data point to a case's history file."""
    history = get_case_history(case_id)
    history.append(record)
    TRACKING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _history_path(case_id).write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Scrape & record
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_metrics(social_data: dict) -> dict:
    """Normalise scraper 社媒数据 into a flat metrics dict.

    Keys in social_data vary by platform; we unify to:
      views, likes, comments, shares
    """
    return {
        "views": social_data.get("播放量") or 0,
        "likes": social_data.get("点赞") or 0,
        "comments": social_data.get("评论") or 0,
        "shares": social_data.get("收藏") or social_data.get("分享") or 0,
    }


def scrape_and_record(case_id: str, force: bool = False) -> dict | None:
    """Scrape a tracked URL and append a history record. Returns the new record,
    or None if the URL could not be scraped.
    """
    case = get_case_by_id(case_id)
    if not case:
        return None

    from engine.scraper import scrape

    try:
        data = scrape(case["url"])
    except Exception as e:
        record = {
            "ts": datetime.now().isoformat(),
            "platform": case.get("platform", "?"),
            "views": 0, "likes": 0, "comments": 0, "shares": 0,
            "_error": str(e)[:200],
        }
        _append_history(case_id, record)
        return record

    social = data.get("社媒数据", {})
    metrics = _extract_metrics(social)
    record = {
        "ts": datetime.now().isoformat(),
        "platform": data.get("来源平台", case.get("platform", "?")),
        **metrics,
    }
    _append_history(case_id, record)
    return record


# ═══════════════════════════════════════════════════════════════════════════════
# Delta computation
# ═══════════════════════════════════════════════════════════════════════════════

def compute_delta(case_id: str) -> dict | None:
    """Compare the latest two history records. Returns per-metric deltas, or None
    if fewer than 2 records exist.

    Return shape: {
        "views":  {"prev": N, "curr": M, "delta_pct": +12.5},
        "likes":  ...,
        ...
    }
    """
    history = get_case_history(case_id)
    if len(history) < 2:
        return None

    prev, curr = history[-2], history[-1]
    deltas = {}
    for key in ("views", "likes", "comments", "shares"):
        pv = prev.get(key, 0) or 0
        cv = curr.get(key, 0) or 0
        if pv > 0:
            delta_pct = round((cv - pv) / pv * 100, 1)
        elif cv > 0:
            delta_pct = None  # new metric, can't compute %
        else:
            delta_pct = 0.0
        deltas[key] = {"prev": pv, "curr": cv, "delta_pct": delta_pct}
    return deltas


def check_alerts(case_id: str) -> list[dict]:
    """Check all alert rules against the latest delta. Returns triggered alerts.

    Each triggered alert: {metric, metric_label, threshold, prev, curr, growth_pct, case_label, url}
    """
    case = get_case_by_id(case_id)
    if not case:
        return []

    alerts_cfg = case.get("alerts", [])
    if not alerts_cfg:
        return []

    delta = compute_delta(case_id)
    if not delta:
        return []

    # Dedup: same case+metric within 1 hour
    now = _time_module.time()
    triggered = []
    for alert in alerts_cfg:
        metric = alert.get("metric", "")
        threshold = alert.get("threshold", 0.5)
        d = delta.get(metric)
        if not d:
            continue
        if d["delta_pct"] is None:
            continue
        if d["delta_pct"] >= threshold * 100:
            # Dedup key
            dup_key = f"{case_id}:{metric}"
            _last = _alert_dedup.get(dup_key, 0)
            if now - _last < 3600:
                continue
            _alert_dedup[dup_key] = now
            triggered.append({
                "metric": metric,
                "metric_label": _METRIC_MAP.get(metric, metric),
                "threshold": threshold,
                "prev": d["prev"],
                "curr": d["curr"],
                "growth_pct": d["delta_pct"],
                "case_label": case.get("label", case_id),
                "url": case.get("url", ""),
            })
    return triggered


_alert_dedup: dict[str, float] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# Tracking scheduler status
# ═══════════════════════════════════════════════════════════════════════════════

_tracking_status: dict = {
    "running": False,
    "last_check": "",
    "active_cases": 0,
    "total_scrapes_today": 0,
    "_today": "",
    "_count": 0,
}

TRACKING_STATUS_PATH = OUTPUTS_DIR / "tracking_status.json"


def get_tracking_status() -> dict:
    """Return tracking scheduler status dict."""
    import copy
    return copy.deepcopy(_tracking_status)


def _write_tracking_status():
    try:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        status_out = {k: v for k, v in _tracking_status.items() if not k.startswith("_")}
        TRACKING_STATUS_PATH.write_text(
            json.dumps(status_out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# TrackingScheduler — background thread for automatic re-scraping
# ═══════════════════════════════════════════════════════════════════════════════

import threading


def _is_due(case: dict, history: list[dict]) -> bool:
    """Check if a tracking case is due for re-scraping."""
    interval_min = case.get("interval_minutes", 120)
    if not history:
        return True  # Never scraped
    try:
        last_ts_str = history[-1].get("ts", "")
        if last_ts_str:
            last_ts = datetime.fromisoformat(last_ts_str)
            elapsed = (datetime.now() - last_ts).total_seconds()
            return elapsed >= interval_min * 60
    except (ValueError, OSError):
        pass
    return True


class TrackingScheduler(threading.Thread):
    """Background thread that periodically checks and re-scrapes tracking cases.

    Runs every 60 seconds. For each enabled case, checks if enough time has
    elapsed since the last scrape. Designed to run inside Streamlit via
    @st.cache_resource alongside SchedulerThread.
    """

    _instance = None

    def __init__(self):
        super().__init__(daemon=True, name="tracking-scheduler")
        self._stop_event = threading.Event()
        TrackingScheduler._instance = self

    def run(self):
        _tracking_status["running"] = True

        while not self._stop_event.is_set():
            try:
                cases = get_all_enabled_cases()
                _tracking_status["active_cases"] = len(cases)
                _tracking_status["last_check"] = datetime.now().isoformat()

                for case in cases:
                    if self._stop_event.is_set():
                        break
                    history = get_case_history(case["id"])
                    if _is_due(case, history):
                        try:
                            record = scrape_and_record(case["id"])
                            if record and not record.get("_error"):
                                # Check and fire alerts
                                triggered = check_alerts(case["id"])
                                if triggered:
                                    from shared.notify import send_feishu_card
                                    for t in triggered:
                                        send_feishu_card(
                                            title=f"⚠️ 高危追踪告警 — {t['case_label'][:40]}",
                                            body_text=(
                                                f"**{t['metric_label']}** 增长 **{t['growth_pct']}%**，"
                                                f"超过阈值 **{int(t['threshold']*100)}%**\n"
                                                f"当前: {t['curr']:,} | 上次: {t['prev']:,}\n"
                                                f"链接: {t['url']}"
                                            ),
                                            level="warning",
                                        )
                                today = datetime.now().strftime("%Y-%m-%d")
                                if _tracking_status.get("_today") == today:
                                    _tracking_status["_count"] += 1
                                else:
                                    _tracking_status["_today"] = today
                                    _tracking_status["_count"] = 1
                                _tracking_status["total_scrapes_today"] = _tracking_status["_count"]
                        except Exception:
                            pass

                _write_tracking_status()
            except Exception:
                pass

            # Sleep in 5s increments so we can stop cleanly
            for _ in range(12):
                if self._stop_event.is_set():
                    break
                _time_module.sleep(5)

        _tracking_status["running"] = False
        _write_tracking_status()

    def stop(self):
        _tracking_status["running"] = False
        self._stop_event.set()
