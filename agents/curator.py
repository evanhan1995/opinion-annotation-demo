# -*- coding: utf-8 -*-
"""
舆情指挥系统 — Curator Agent (知识库保管员)

Responsibility (PRD §5.5):
  1. KB four-system management: foundation/cases/reports/authors
  2. Case ingestion: generate case page with 4 tags
  3. 3D index: platform × severity × status
  4. Handler status sync: update_case_status()
  5. Cross-platform linking (linker)
  6. KB Q&A (扫地僧)
  7. Human correction handling

Isolation constraints:
  - MUST NOT modify annotation content (read-only ingest)
  - MUST NOT actively change case status (only respond to Handler sync)
  - MUST NOT judge content relevance (Analyst's job)

Model: DeepSeek (Q&A search) + template-based case generation (no LLM needed).
"""
import io
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agents.shared import (
    get_llm, load_prompt, PROJECT_ROOT, WIKI_DIR,
    RawData, Annotation, KBEntry,
    rawdata_to_engine_dict, annotation_to_engine_dict,
)

CURATOR_SYSTEM_PROMPT = ""


def _get_prompt() -> str:
    global CURATOR_SYSTEM_PROMPT
    if not CURATOR_SYSTEM_PROMPT:
        CURATOR_SYSTEM_PROMPT = load_prompt("curator_system")
    return CURATOR_SYSTEM_PROMPT


# ── Wiki paths ─────────────────────────────────────────────────────────
CASES_DIR = WIKI_DIR / "cases"
FOUNDATION_DIR = WIKI_DIR / "foundation"
REPORTS_DAILY_DIR = WIKI_DIR / "reports" / "daily"
REPORTS_MONTHLY_DIR = WIKI_DIR / "reports" / "monthly"
AUTHORS_DIR = WIKI_DIR / "authors"
INDEX_PATH = WIKI_DIR / "index.md"
LOG_PATH = WIKI_DIR / "log.md"


# ── Case ingestion ─────────────────────────────────────────────────────
def _generate_case_id() -> str:
    """Generate sequential case ID. Delegates to canonical ingestor implementation."""
    from engine.ingestor import get_next_case_id
    return get_next_case_id()


def _build_case_frontmatter(raw: RawData, annotation: Annotation, case_id: str,
                            notes: str = "", init_status: str = "待跟进") -> str:
    """Build YAML frontmatter for a case page with 4 tags."""
    ingested_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "---",
        f"case_id: {case_id}",
        f"url: {raw.url}",
        f"platform: {raw.platform}",
        f"severity: {annotation.severity}",
        f"status: {init_status}",
        f"category: {annotation.category or '其他'}",
        f"ingested_at: {ingested_at}",
        f"title: {raw.title}",
        f"author: {raw.author}",
        f"publish_time: {raw.publish_time}",
    ]
    if notes:
        lines.append(f"notes: {notes}")
    lines.append("---")
    return "\n".join(lines)


def _build_case_body(raw: RawData, annotation: Annotation, notes: str = "",
                     init_status: str = "待跟进") -> str:
    """Build the markdown body of a case page."""
    parts = [
        f"# {raw.title or '无标题'}",
        "",
        f"- **平台**: {raw.platform}",
        f"- **严重度**: {annotation.severity}",
        f"- **情感**: {annotation.sentiment}",
        f"- **风险标签**: {', '.join(annotation.risk_tags) if annotation.risk_tags else '无'}",
        f"- **分流建议**: {annotation.triage}",
        f"- **处置状态**: {init_status}",
    ]
    if notes:
        parts.append(f"- **备注**: {notes}")
    parts.extend([
        "",
        "## 内容摘要",
        annotation.summary,
        "",
        "## 原始内容",
        raw.content[:2000] if raw.content else "(无内容)",
        "",
        "## 处置记录",
        f"| 时间 | 状态变更 | 操作人 | 备注 |",
        f"|------|---------|--------|------|",
        f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} | 入库 → {init_status} | 系统 | {notes or '案例入库'} |",
    ])
    if raw.comments_raw:
        parts.append("\n## 评论区")
        parts.extend(f"- {c[:200]}" for c in raw.comments_raw[:20])
    return "\n".join(parts)


def ingest(raw: RawData, annotation: Annotation, notes: str = "",
           init_status: str = "待跟进") -> KBEntry:
    """Ingest a case into the knowledge base.

    Phase 2: delegates to engine/ingestor.py for full pipeline (dedup, index, author lib, archive).

    Called by Orchestrator after Analyst + Handler complete.
    """
    CASES_DIR.mkdir(parents=True, exist_ok=True)

    # Try full engine pipeline first
    try:
        from engine.ingestor import ingest as engine_ingest
        engine_scraped = rawdata_to_engine_dict(raw)
        engine_annotation = annotation_to_engine_dict(annotation)
        result = engine_ingest(engine_scraped, engine_annotation, raw.url,
                               notes=notes, init_status=init_status)
        case_file = result.get("case_file", "")
        case_id = case_file.replace(".md", "") if case_file else _generate_case_id()
        case_path = CASES_DIR / case_file if case_file else CASES_DIR / f"{case_id}.md"
    except Exception:
        # Fallback to local case generation
        case_id = _generate_case_id()
        frontmatter = _build_case_frontmatter(raw, annotation, case_id,
                                              notes=notes, init_status=init_status)
        body = _build_case_body(raw, annotation, notes=notes, init_status=init_status)
        case_path = CASES_DIR / f"{case_id}.md"
        case_path.write_text(frontmatter + "\n" + body, encoding="utf-8")

    # Append to log
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_entry = f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} | {case_id} | {raw.platform} | {annotation.severity} | {init_status} | ingest |\n"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        if not LOG_PATH.exists() or LOG_PATH.stat().st_size == 0:
            f.write("| 时间 | Case ID | 平台 | 严重度 | 状态 | 操作 |\n")
            f.write("|------|---------|------|--------|------|------|\n")
        f.write(log_entry)

    return KBEntry(
        case_id=case_id, url=raw.url, platform=raw.platform,
        severity=annotation.severity, status=init_status,
        ingested_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        title=raw.title, file_path=str(case_path),
    )


# ── Handler status sync ────────────────────────────────────────────────
def update_case_status(case_id: str, new_status: str, notes: str = "") -> dict:
    """Update case status in KB frontmatter + index + log.

    PRD: "Handler更新处置状态 → Curator.update_case_status()"
    Called ONLY by Orchestrator (on behalf of Handler).
    """
    # Support both flat and subdirectory layouts
    case_path = CASES_DIR / f"{case_id}.md"
    if not case_path.exists():
        for sub in CASES_DIR.iterdir():
            if sub.is_dir():
                alt = sub / f"{case_id}.md"
                if alt.exists():
                    case_path = alt
                    break
    if not case_path.exists():
        return {"success": False, "error": f"Case not found: {case_id}"}

    text = case_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {"success": False, "error": f"No frontmatter in {case_id}"}

    fm = parts[1]
    old_status = ""
    if m := __import__("re").search(r"^status:\s*(.+)$", fm, __import__("re").MULTILINE):
        old_status = m.group(1).strip()

    # Update status in frontmatter
    import re
    if re.search(r"^status:", fm, re.MULTILINE):
        fm_updated = re.sub(r"^status:.*$", f"status: {new_status}", fm, flags=re.MULTILINE)
    else:
        # No status field yet — append one before the closing ---
        fm_updated = fm.rstrip() + f"\nstatus: {new_status}"

    # Also update notes if provided
    if notes:
        if re.search(r"^notes:", fm_updated, re.MULTILINE):
            fm_updated = re.sub(r"^notes:.*$", f"notes: {notes}", fm_updated, flags=re.MULTILINE)
        else:
            fm_updated = fm_updated.rstrip() + f"\nnotes: {notes}"

    updated_text = f"---{fm_updated}---{parts[2]}"
    case_path.write_text(updated_text, encoding="utf-8")

    # Try to update case index
    try:
        from engine.index_mgr import update_case_index
        update_case_index(f"{case_id}.md", parts[2].split("severity:")[1].split("\n")[0].strip() if "severity:" in parts[2] else "P2",
                          "已处理" if new_status == "已处理" else "内部研判",
                          case_id, case_path.read_text(encoding="utf-8").split("title:")[0].strip() if "title:" in case_path.read_text(encoding="utf-8") else "",
                          [], [], "")
    except Exception:
        pass

    # Log
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = f"| {timestamp} | {case_id} | - | - | {new_status} | status_update | {notes} |\n"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(log_entry)

    return {
        "success": True, "case_id": case_id, "old_status": old_status,
        "new_status": new_status, "timestamp": timestamp,
    }


# ── Structured query API (PRD: Curator owns all KB read access) ────────

def _find_case_files() -> list[Path]:
    """Find all case-*.md files, supporting both flat and subdirectory layout."""
    if not CASES_DIR.exists():
        return []
    files = list(CASES_DIR.glob("case-*.md"))
    # Also recurse into platform subdirectories (Phase B layout)
    for sub in CASES_DIR.iterdir():
        if sub.is_dir():
            files.extend(sub.glob("case-*.md"))
    return sorted(files)


def _parse_case_frontmatter(filepath: Path) -> dict:
    """Parse frontmatter from a case file. Returns dict with keys:
    case_id, title, severity, status, platform, url, sentiment, category,
    created, ingested_at, assigned_date, notes, author, filename.
    """
    import re
    result = {
        "case_id": filepath.stem, "filename": filepath.name,
        "title": "", "severity": "", "status": "待跟进", "platform": "",
        "url": "", "sentiment": "", "category": "", "created": "",
        "ingested_at": "", "assigned_date": "", "notes": "", "author": "",
    }
    try:
        text = filepath.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) < 3:
            return result
        fm = parts[1]
        for key in result:
            m = re.search(rf"^{key}:\s*(.+)$", fm, re.MULTILINE)
            if m:
                result[key] = m.group(1).strip()
        # ingestor writes `created`, curator queries `ingested_at` — bridge them
        if not result["ingested_at"] and result["created"]:
            result["ingested_at"] = result["created"]
    except Exception:
        pass
    return result


def query_cases(filters: dict | None = None) -> list[dict]:
    """Query cases from the knowledge base with optional filters.

    Args:
        filters: optional dict with keys: status, severity, platform,
                 date_from, date_to, assigned_before (ISO date strings)

    Returns list of case dicts. This is the ONLY legal way for other agents
    to read case data — no direct file access.
    """
    filters = filters or {}
    cases = []
    for fp in _find_case_files():
        c = _parse_case_frontmatter(fp)
        # Apply filters
        if "status" in filters and c["status"] != filters["status"]:
            continue
        if "severity" in filters and c["severity"] not in filters["severity"]:
            continue
        if "platform" in filters and c["platform"] != filters["platform"]:
            continue
        if "date_from" in filters and c["ingested_at"] < filters["date_from"]:
            continue
        if "date_to" in filters and c["ingested_at"] > filters["date_to"]:
            continue
        if "assigned_before" in filters and c["assigned_date"]:
            if c["assigned_date"] >= filters["assigned_before"]:
                continue
        cases.append(c)
    return cases


def query_stats(date_from: str = "", date_to: str = "") -> dict:
    """Return aggregate KB statistics. One call replaces full file scan.

    Args:
        date_from: optional ISO date string to filter cases ingested on/after this date
        date_to: optional ISO date string to filter cases ingested on/before this date

    Returns dict with: total_cases, severity_dist, sentiment_dist,
    platform_dist, status_dist, top_categories, p0_p1_list.
    """
    severity_dist = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    sentiment_dist = {"正面": 0, "中性": 0, "负面": 0}
    platform_dist: dict[str, int] = {}
    status_dist = {"待跟进": 0, "处理中": 0, "已处理": 0, "已放弃": 0, "忽略": 0}
    categories: dict[str, int] = {}
    p0_p1_list: list[dict] = []

    for fp in _find_case_files():
        c = _parse_case_frontmatter(fp)

        # Date range filter
        if date_from and c["ingested_at"] < date_from:
            continue
        if date_to and c["ingested_at"] > date_to:
            continue

        sev = c["severity"]
        if sev in severity_dist:
            severity_dist[sev] += 1

        sent = c["sentiment"]
        if sent in sentiment_dist:
            sentiment_dist[sent] += 1

        pf = c["platform"]
        if pf:
            platform_dist[pf] = platform_dist.get(pf, 0) + 1

        st = c["status"] or "待跟进"
        if st in status_dist:
            status_dist[st] += 1

        cat = c["category"]
        if cat and cat != "其他":
            categories[cat] = categories.get(cat, 0) + 1

        if sev in ("P0", "P1"):
            p0_p1_list.append({
                "severity": sev, "title": c["title"],
                "platform": pf, "status": st,
            })

    return {
        "total_cases": sum(severity_dist.values()),
        "severity_dist": severity_dist,
        "sentiment_dist": sentiment_dist,
        "platform_dist": platform_dist,
        "status_dist": status_dist,
        "top_categories": sorted(categories, key=categories.get, reverse=True)[:5],
        "p0_p1_list": p0_p1_list,
    }


def append_timeline(case_id: str, from_status: str, to_status: str,
                    notes: str = "", operator: str = "系统") -> dict:
    """Append a disposition timeline entry to a case file.

    This is the ONLY legal way to write timeline entries — Orchestrator
    must call this instead of writing case files directly.

    Also auto-sets assigned_date when transitioning 待跟进→处理中.
    """
    import re
    from datetime import date

    # Support both flat and subdirectory layouts
    case_path = CASES_DIR / f"{case_id}.md"
    if not case_path.exists():
        for sub in CASES_DIR.iterdir():
            if sub.is_dir():
                alt = sub / f"{case_id}.md"
                if alt.exists():
                    case_path = alt
                    break

    if not case_path.exists():
        return {"success": False, "error": f"Case not found: {case_id}"}

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    timeline_entry = f"\n| {timestamp} | {from_status} → {to_status} | {operator} | {notes} |"

    text = case_path.read_text(encoding="utf-8")
    if "## 处置时间线" in text:
        text = text.rstrip() + timeline_entry
    else:
        header = "\n\n## 处置时间线\n\n| 时间 | 状态变更 | 操作人 | 备注 |\n|------|---------|--------|------|"
        text = text.rstrip() + header + timeline_entry

    # Auto-set assigned_date on 待跟进→处理中 transition
    if from_status == "待跟进" and to_status == "处理中":
        today = date.today().isoformat()
        if "assigned_date:" not in text.split("---", 2)[1] if "---" in text else "":
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm = parts[1]
                if "assigned_date:" not in fm:
                    fm += f"\nassigned_date: {today}"
                text = f"---{fm}---{parts[2]}"

    # Update notes in frontmatter AND body ## 处置备注 section
    if notes:
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            body = parts[2]
            if re.search(r"^notes:", fm, re.MULTILINE):
                fm = re.sub(r"^notes:.*$", f"notes: {notes}", fm, flags=re.MULTILINE)
            else:
                fm = fm.rstrip() + f"\nnotes: {notes}"
            # Sync body ## 处置备注 section
            if "## 处置备注" in body:
                body = re.sub(
                    r'(## 处置备注\n\n).*?(?=\n## |\Z)',
                    r'\1' + notes,
                    body,
                    flags=re.DOTALL,
                )
            else:
                last_h2 = list(re.finditer(r'\n## ', body))
                if last_h2:
                    pos = last_h2[-1].start()
                    body = body[:pos] + f"\n\n## 处置备注\n\n{notes}" + body[pos:]
                else:
                    body = body.rstrip() + f"\n\n## 处置备注\n\n{notes}\n"
            text = f"---{fm}---{body}"

    case_path.write_text(text, encoding="utf-8")
    return {"success": True, "case_id": case_id, "timestamp": timestamp}


# ── KB Q&A ─────────────────────────────────────────────────────────────
def search(query: str, top_n: int = 5) -> list[dict]:
    """Search the knowledge base for relevant cases/concepts.

    Delegates to engine/agent.py search_wiki() for bigram search.
    """
    try:
        from engine.agent import search_wiki
        results = search_wiki(query, top_n)
        return [{"title": r["title"], "snippet": r["excerpt"][:200], "url": r["path"]} for r in results]
    except Exception:
        return [{"title": "search error", "snippet": f"Query: {query}", "url": ""}]


def answer_query(query: str) -> str:
    """Full KB Q&A with LLM via engine/agent.py ask_agent()."""
    try:
        from engine.annotate import load_config
        from engine.agent import ask_agent
        config = load_config()
        result = ask_agent(query, config, [])
        if isinstance(result, dict):
            return result.get("answer", str(result))
        return str(result)
    except Exception as e:
        return f"知识库问答出错: {e}"
