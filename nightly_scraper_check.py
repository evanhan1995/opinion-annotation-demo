"""Nightly XHS scraper validation.
Runs unit tests + dry-run scrape, writes JSON report.
Suitable for Windows Task Scheduler or cron.
Usage: python nightly_scraper_check.py
"""

import json
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
REPORT_DIR = PROJECT_DIR / "outputs" / "nightly"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
report_path = REPORT_DIR / f"scraper_check_{ts}.json"

def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_DIR))
    return r.returncode, (r.stdout + "\n" + r.stderr).strip()

report = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "test": {"exit_code": None, "output": ""},
    "scrape": {"has_content": False, "content_len": 0, "has_comments": False, "comment_count": 0, "platform": None, "title": ""},
    "status": "fail",
}

# Step 1: run XHS adapter unit tests
print("[1/2] Running XHS unit tests...")
exit_code, output = run([sys.executable, "-m", "pytest", "tests/test_xhs_adapter.py", "-v", "--tb=short"])
report["test"]["exit_code"] = exit_code
report["test"]["output"] = output[-2000:]
tests_ok = exit_code == 0

# Step 2: dry-run scrape one known post
print("[2/2] Dry-run XHS scrape...")
try:
    sys.path.insert(0, str(PROJECT_DIR))
    from engine.scraper import scrape
    result = scrape("https://www.xiaohongshu.com/explore/69ff2eea000000001f005fcc")
    report["scrape"]["has_content"] = bool(result.get("content"))
    report["scrape"]["content_len"] = len(result.get("content", ""))
    report["scrape"]["has_comments"] = bool(result.get("comments"))
    report["scrape"]["comment_count"] = len(result.get("comments", []))
    report["scrape"]["platform"] = result.get("platform", "")
    report["scrape"]["title"] = (result.get("title") or "")[:120]
except Exception as e:
    report["scrape"]["error"] = str(e)

report["status"] = "pass" if (tests_ok and report["scrape"]["has_content"]) else "fail"

with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"Report: {report_path}")
print(f"Status: {report['status'].upper()}")
sys.exit(0 if report["status"] == "pass" else 1)
