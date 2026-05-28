# -*- coding: utf-8 -*-
"""
舆情指挥系统 — Monitor Agent (监测员)

Responsibility (PRD §5.1):
  1. Load keywords from monitor_keywords.json
  2. Search each keyword × platform (single sort: default relevance or by date)
  3. Deduplicate against previous crawl archives
  4. Export results to Excel + archive to raw/monitor/
  5. Track keyword hit rates, generate optimization suggestions
  6. Brand keyword SEO snapshot (PRD M-10)

Isolation constraints:
  - MUST NOT call Scraper to fetch details (Orchestrator handles that)
  - MUST NOT write to wiki/cases/ (Curator's domain)
  - MUST NOT modify monitor_keywords.json (read-only; suggestions only)

Model: No LLM needed — all logic is pure code (search APIs + dedup + Excel).
"""
import io
import json
import re
import sys
from concurrent import futures
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Hard timeout per platform search call (seconds).  A single yt-dlp
# ytsearch / ytsearchdate call normally takes 2-8 s on a decent
# connection; 60 s is generous enough for slow networks but prevents
# indefinite hangs in background threads.
_SEARCH_TIMEOUT = 60

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agents.shared import PROJECT_ROOT, RAW_DIR, OUTPUTS_DIR


# ── Dataclasses ────────────────────────────────────────────────────────
@dataclass
class SearchResult:
    """A single search result item."""
    platform: str
    keyword_id: str
    keyword: str
    sort_type: str           # date | hot
    title: str
    url: str
    author: str = ""
    publish_time: str = ""
    engagement: int = 0      # likes + comments + shares
    snippet: str = ""


@dataclass
class KeywordResult:
    """Aggregated results for one keyword × platform."""
    keyword_id: str
    keyword: str
    platform: str
    date_results: list[SearchResult] = field(default_factory=list)
    hot_results: list[SearchResult] = field(default_factory=list)
    new_items: list[SearchResult] = field(default_factory=list)  # after dedup


@dataclass
class MonitorStats:
    """Statistics for a monitor job."""
    keywords_searched: int = 0
    platforms_queried: int = 0
    total_fetched: int = 0
    total_new: int = 0
    dedup_rate: float = 0.0
    hit_rates: dict = field(default_factory=dict)   # {kw_id: {platform: rate}}


@dataclass
class MonitorHarvest:
    """Complete output of a monitor job (PRD §5.1)."""
    job_id: str
    started_at: str
    finished_at: str
    keyword_results: list[KeywordResult] = field(default_factory=list)
    total_fetched: int = 0
    total_new: int = 0
    dedup_rate: float = 0.0
    excel_path: str = ""
    stats: Optional[MonitorStats] = None
    errors: list[str] = field(default_factory=list)


# ── Config loading ─────────────────────────────────────────────────────
def load_keywords() -> list[dict]:
    """Load and return active keyword entries from monitor_keywords.json."""
    path = PROJECT_ROOT / "monitor_keywords.json"
    if not path.exists():
        return []
    cfg = json.loads(path.read_text(encoding="utf-8"))
    return [kw for kw in cfg.get("keywords", []) if kw.get("active", True)]


# ── Platform search ────────────────────────────────────────────────────
def _search_douyin(keyword: str, sort_type: str, count: int = 30) -> list[SearchResult]:
    """Search Douyin via TikTokDownloader Search API.

    sort_type: 'date' → sort_type=2 (最新), 'hot' → sort_type=1 (最多点赞)
    """
    _TT_DOWNLOADER_PATH = Path("D:/Claude code/Github skills/TikTokDownloader")
    if not _TT_DOWNLOADER_PATH.exists():
        return []

    import sys as _sys
    _tt_src = str(_TT_DOWNLOADER_PATH)
    if _tt_src not in _sys.path:
        _sys.path.insert(0, _tt_src)

    try:
        from src.application import TikTokDownloader as _TTApp
    except ImportError:
        return []

    try:
        from src.interface import Search as _Search
    except ImportError:
        return []

    import asyncio

    async def _search():
        async with _TTApp() as app:
            app.check_config()
            await app.check_settings(False)
            search = _Search(
                app.parameter,
                keyword=keyword,
                pages=max(1, count // 15),
                sort_type=2 if sort_type == "date" else 1,
            )
            result = await search.run(single_page=True)
            return result

    try:
        raw_results = asyncio.run(_search())
    except Exception:
        return []

    if not raw_results:
        return []

    results = []
    for item in (raw_results if isinstance(raw_results, list) else []):
        results.append(SearchResult(
            platform="douyin",
            keyword_id="",
            keyword=keyword,
            sort_type=sort_type,
            title=item.get("desc", "") or item.get("title", ""),
            url=item.get("url", "") or f"https://www.douyin.com/video/{item.get('aweme_id', '')}",
            author=item.get("author", {}).get("nickname", "") if isinstance(item.get("author"), dict) else "",
            publish_time=item.get("create_time", ""),
            engagement=(item.get("statistics", {}) or {}).get("digg_count", 0),
            snippet=(item.get("desc", "") or "")[:200],
        ))
    return results[:count]


def _search_youtube(keyword: str, sort_type: str, count: int = 30) -> list[SearchResult]:
    """Search YouTube via yt-dlp ytsearch.

    sort_type='date' → ytsearch + client-side sort by upload_date DESC
                       (ytsearchdate is broken in yt-dlp >= 2026.03.17)
    sort_type='hot'  → ytsearch (default relevance sort)
    """
    try:
        import yt_dlp
    except ImportError:
        return []

    # Always use ytsearch — ytsearchdate extractor was removed in yt-dlp v2026.03.17.
    # For date-sorted results we sort client-side by upload_date after extraction.
    search_query = f"ytsearch{count}:{keyword}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "socket_timeout": 30,
    }

    results: list[SearchResult] = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            for entry in info.get("entries", []) or []:
                vid = entry.get("id", "")
                results.append(SearchResult(
                    platform="youtube",
                    keyword_id="",
                    keyword=keyword,
                    sort_type=sort_type,
                    title=entry.get("title", ""),
                    url=f"https://www.youtube.com/watch?v={vid}" if vid else entry.get("url", ""),
                    author=entry.get("channel", "") or entry.get("uploader", ""),
                    publish_time=entry.get("upload_date", "") or "",
                    engagement=(entry.get("view_count") or 0),
                    snippet=entry.get("description", "")[:200] if entry.get("description") else "",
                ))
    except Exception:
        pass

    # Client-side date sort: ytsearchdate extractor is broken, so we
    # fetch via ytsearch and sort by upload_date descending ourselves.
    if sort_type == "date" and results:
        results.sort(key=lambda r: r.publish_time, reverse=True)

    return results


def _search_xiaohongshu(keyword: str, sort_type: str, count: int = 30) -> list[SearchResult]:
    """Search XHS via Playwright with cached cookies.

    sort_type: 'date' → time_descending (最新), 'hot' → general (最热)
    Requires valid login cookies in engine/.xhs_cookies.json.
    Graceful degradation: returns empty on any failure.
    """
    from urllib.parse import quote

    sort_param = "time_descending" if sort_type == "date" else "general"
    search_url = (
        f"https://www.xiaohongshu.com/search_result?"
        f"keyword={quote(keyword)}&sort={sort_param}"
    )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    # Load cached cookies (use absolute path, not CWD-relative)
    cookie_file = PROJECT_ROOT / "engine" / ".xhs_cookies.json"
    playwright_cookies = []
    if cookie_file.exists():
        try:
            import json as _json
            cdata = _json.loads(cookie_file.read_text(encoding="utf-8"))
            cookie_str = cdata.get("cookie_str", "")
            for pair in cookie_str.split("; "):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    playwright_cookies.append({
                        "name": k.strip(), "value": v.strip(),
                        "domain": ".xiaohongshu.com", "path": "/",
                    })
        except Exception:
            pass

    if not playwright_cookies:
        return []  # No cookies → would hit login wall

    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            ctx.add_cookies(playwright_cookies)
            page = ctx.new_page()
            page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            cards = page.query_selector_all("section.note-item, a[href*='/explore/']")
            for card in cards[:count]:
                try:
                    link_el = card.query_selector("a[href*='/explore/']")
                    href = link_el.get_attribute("href") if link_el else ""
                    url = f"https://www.xiaohongshu.com{href}" if href.startswith("/") else href

                    title_el = card.query_selector(".title, .note-title, a.title, span.title")
                    title = title_el.inner_text().strip() if title_el else ""

                    author_el = card.query_selector(".author .name, .nickname, .username")
                    author = author_el.inner_text().strip() if author_el else ""

                    likes_el = card.query_selector(".like-count, .count, .like span, span.count")
                    likes_text = likes_el.inner_text().strip() if likes_el else "0"

                    results.append(SearchResult(
                        platform="xiaohongshu",
                        keyword_id="", keyword=keyword, sort_type=sort_type,
                        title=title[:200], url=url, author=author,
                        engagement=int(re.sub(r'\D', '', likes_text) or 0),
                    ))
                except Exception:
                    continue

            browser.close()
    except Exception:
        pass

    return results[:count]


PLATFORM_SEARCHERS = {
    "douyin": _search_douyin,
    "youtube": _search_youtube,
    "xiaohongshu": _search_xiaohongshu,
}


def _search_with_timeout(searcher, keyword: str, sort_type: str, count: int) -> list[SearchResult]:
    """Run a platform search in a thread with a hard timeout.

    yt-dlp / Playwright calls can block indefinitely in background threads
    even with socket_timeout set.  This wraps each call in a future so we
    can enforce a wall-clock deadline.
    """
    executor = futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = executor.submit(searcher, keyword, sort_type, count)
        try:
            return fut.result(timeout=_SEARCH_TIMEOUT)
        except futures.TimeoutError:
            return []
        except Exception:
            return []
    finally:
        executor.shutdown(wait=False)


# ── Deduplication ──────────────────────────────────────────────────────
def _load_previous_urls(keyword_id: str, platform: str) -> set:
    """Load ALL previously archived URLs across all dates for cross-day dedup."""
    archive_root = RAW_DIR / "monitor"
    if not archive_root.exists():
        return set()
    urls = set()
    for date_dir in archive_root.iterdir():
        if not date_dir.is_dir():
            continue
        for f in date_dir.glob(f"{keyword_id}_{platform}_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for item in data:
                    if isinstance(item, dict) and "url" in item:
                        urls.add(item["url"])
            except Exception:
                pass
    return urls


def _archive_results(results: list[SearchResult], date_str: str, keyword_id: str, platform: str, sort_type: str):
    """Archive search results to raw/monitor/YYYY-MM-DD/."""
    archive_dir = RAW_DIR / "monitor" / date_str
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / f"{keyword_id}_{platform}_{sort_type}.json"
    data = [{"title": r.title, "url": r.url, "author": r.author,
             "publish_time": r.publish_time, "engagement": r.engagement} for r in results]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Excel export ───────────────────────────────────────────────────────
def _export_excel(harvest: MonitorHarvest) -> str:
    """Export MonitorHarvest to Excel with yellow highlights for new items."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment
    except ImportError:
        path = OUTPUTS_DIR / f"monitor_{harvest.job_id}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"Monitor Job: {harvest.job_id}", f"Total: {harvest.total_fetched}, New: {harvest.total_new}"]
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Monitor {harvest.job_id}"

    headers = ["来源平台", "关键词ID", "关键词", "排序方式", "标题", "URL", "作者", "发布时间", "互动量"]
    header_font = Font(bold=True)
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font

    row = 2
    new_urls = {(r.url) for kr in harvest.keyword_results for r in kr.new_items}

    for kr in harvest.keyword_results:
        for r in kr.date_results + kr.hot_results:
            values = [r.platform, kr.keyword_id, kr.keyword, r.sort_type,
                      r.title[:200], r.url, r.author, r.publish_time, r.engagement]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                if r.url in new_urls:
                    cell.fill = yellow_fill
            row += 1

    path = OUTPUTS_DIR / f"monitor_{harvest.job_id}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))
    return str(path)


# ── Main entry point ───────────────────────────────────────────────────
def execute_job(progress_callback=None, sort_preference: str = "default") -> MonitorHarvest:
    """Execute a full monitor job: search → dedup → archive → Excel.

    Args:
        progress_callback: Optional callable(details_str) for per-keyword
            progress reporting. Called before each platform search.
        sort_preference: "default" (relevance/popularity) or "date" (time sort).
            Maps to internal sort_type "hot" / "date" respectively.

    Called by Orchestrator.run_active_monitor() and pipeline._run_pipeline().
    """
    # Map user-facing preference to internal sort_type
    _sort_type = "date" if sort_preference == "date" else "hot"

    job_id = datetime.now().strftime("%Y%m%d_%H%M")
    date_str = datetime.now().strftime("%Y-%m-%d")
    started = datetime.now().isoformat()
    keywords = load_keywords()
    harvest = MonitorHarvest(job_id=job_id, started_at=started, finished_at="")

    defaults = json.loads(
        (PROJECT_ROOT / "monitor_keywords.json").read_text(encoding="utf-8")
    ).get("defaults", {"result_count": 30})

    total_pairs = sum(len(kw.get("platforms", [])) for kw in keywords)
    pair_idx = 0

    for kw_entry in keywords:
        kw_id = kw_entry["id"]
        kw_text = kw_entry["keyword"]
        count = kw_entry.get("result_count", defaults.get("result_count", 30))

        for platform in kw_entry.get("platforms", []):
            pair_idx += 1
            searcher = PLATFORM_SEARCHERS.get(platform)
            if searcher is None:
                continue

            if progress_callback:
                progress_callback(f"搜索: {kw_text} @ {platform} ({pair_idx}/{total_pairs})")

            kr = KeywordResult(keyword_id=kw_id, keyword=kw_text, platform=platform)

            # Single search with user-selected sort type (replaced dual date+hot search)
            try:
                results = _search_with_timeout(searcher, kw_text, _sort_type, count)
            except Exception:
                results = []

            # Store results in the appropriate field for backward compat
            if _sort_type == "date":
                kr.date_results = results
            else:
                kr.hot_results = results

            prev_urls = _load_previous_urls(kw_id, platform)
            kr.new_items = [r for r in results if r.url not in prev_urls]

            harvest.total_fetched += len(results)
            harvest.total_new += len(kr.new_items)

            # Archive single result set
            _archive_results(results, date_str, kw_id, platform, _sort_type)

            harvest.keyword_results.append(kr)

    if harvest.total_fetched > 0:
        harvest.dedup_rate = (harvest.total_fetched - harvest.total_new) / harvest.total_fetched

    harvest.finished_at = datetime.now().isoformat()
    harvest.excel_path = _export_excel(harvest)
    harvest.stats = MonitorStats(
        keywords_searched=len(keywords),
        platforms_queried=sum(len(kw.get("platforms", [])) for kw in keywords),
        total_fetched=harvest.total_fetched,
        total_new=harvest.total_new,
        dedup_rate=harvest.dedup_rate,
    )

    return harvest


# ── Feedback learning (Analyst → Monitor) ─────────────────────────────
def record_feedback(keyword_id: str, platform: str, is_relevant: bool, reason: str = ""):
    """Record Analyst relevance feedback for keyword optimization (PRD M-07).

    Called by Orchestrator (not directly by Analyst — isolation constraint).
    """
    feedback_path = PROJECT_ROOT / "outputs" / "keyword_feedback.jsonl"
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "keyword_id": keyword_id,
        "platform": platform,
        "is_relevant": is_relevant,
        "reason": reason,
    }
    with open(feedback_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


