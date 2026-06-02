# -*- coding: utf-8 -*-
"""
MediaCrawler adapter — wraps XiaoHongShuClient for in-process XHS scraping.

Uses MediaCrawler's anti-detection infrastructure (stealth.js + browser args)
combined with our cached cookie system from xhs_fetcher.py.

Architecture:
  Cookie bootstrap (xhs_fetcher.py) → cached .xhs_cookies.json
      → mediacrawler_adapter.py loads cookies → creates XiaoHongShuClient
          → get_note_by_id() for single-note fetch
          → get_note_by_keyword() for search

Usage:
    from engine.mediacrawler_adapter import fetch_xhs_note, search_xhs
    result = fetch_xhs_note("https://www.xiaohongshu.com/explore/xxx")
    results = search_xhs("关键词", count=30)
"""

import io
import json
import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

import engine._compat

# Add MediaCrawler to Python path
_MEDIACRAWLER_PATH = Path("D:/Claude code/MediaCrawler")
if _MEDIACRAWLER_PATH.exists() and str(_MEDIACRAWLER_PATH) not in sys.path:
    sys.path.insert(0, str(_MEDIACRAWLER_PATH))

from media_platform.xhs.client import XiaoHongShuClient
from media_platform.xhs.field import SearchSortType, SearchNoteType
from media_platform.xhs.help import get_search_id, parse_note_info_from_note_url
from media_platform.xhs.exception import DataFetchError, NoteNotFoundError

from engine.ratelimit import get_limiter

from engine.browser_pool import launch_context

ENGINE_DIR = Path(__file__).resolve().parent
COOKIE_FILE = ENGINE_DIR / ".xhs_cookies.json"

_client_lock = threading.Lock()
_client_instance: Optional[XiaoHongShuClient] = None
_browser_context = None
_client_browser = None
_playwright_instance = None


def _run_async(coro):
    """Run an async coroutine safely in any context (with or without running event loop)."""
    import asyncio as _asyncio
    try:
        loop = _asyncio.get_running_loop()
    except RuntimeError:
        return _asyncio.run(coro)

    # Already in an event loop — run in a new thread
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_asyncio.run, coro)
        return future.result(timeout=60)


def _load_cookie_dict() -> Optional[Dict[str, str]]:
    """Load cookie dict from cached file (written by xhs_fetcher bootstrap)."""
    if not COOKIE_FILE.exists():
        return None
    try:
        data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
        cookie_str = data.get("cookie_str", "")
        if not cookie_str:
            return None
        cookie_dict = {}
        for pair in cookie_str.split("; "):
            if "=" in pair:
                k, v = pair.split("=", 1)
                cookie_dict[k.strip()] = v.strip()
        return cookie_dict if cookie_dict else None
    except (json.JSONDecodeError, KeyError):
        return None


def _load_cookie_str() -> Optional[str]:
    """Load raw cookie string from cache."""
    if not COOKIE_FILE.exists():
        return None
    try:
        data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
        return data.get("cookie_str", "") or None
    except (json.JSONDecodeError, KeyError):
        return None


def _get_client() -> Optional[XiaoHongShuClient]:
    """Get or create a singleton XiaoHongShuClient backed by a headless browser.

    The browser context is kept alive across calls. On first call, launches
    a headless Chromium with stealth.js and injects cached cookies.
    """
    global _client_instance, _browser_context, _playwright_instance

    cookie_dict = _load_cookie_dict()
    cookie_str = _load_cookie_str()
    if not cookie_dict or not cookie_str:
        return None

    with _client_lock:
        if _client_instance is not None:
            return _client_instance

        media_crawler_profile = Path(
            "D:/Claude code/MediaCrawler/browser_data/xhs_user_data_dir"
        )
        user_data_dir = str(media_crawler_profile) if media_crawler_profile.exists() else None

        _browser_context, _client_browser, _playwright_instance = launch_context(
            headless=True,
            user_data_dir=user_data_dir,
            stealth=True,
        )

        page = _browser_context.new_page()
        # Navigate to XHS to set domain context for cookies
        page.goto("https://www.xiaohongshu.com", timeout=15000, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        # Inject cookies into browser context
        playwright_cookies = []
        for name, value in cookie_dict.items():
            playwright_cookies.append({
                "name": name, "value": value,
                "domain": ".xiaohongshu.com", "path": "/",
            })
        _browser_context.add_cookies(playwright_cookies)

        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.xiaohongshu.com",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": "https://www.xiaohongshu.com/",
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
            "Cookie": cookie_str,
        }

        _client_instance = XiaoHongShuClient(
            headers=headers,
            playwright_page=page,
            cookie_dict=cookie_dict,
        )
        return _client_instance


def _cleanup_client():
    """Close the singleton client and browser. Called on shutdown or error."""
    global _client_instance, _browser_context, _client_browser, _playwright_instance
    with _client_lock:
        if _client_browser:
            try:
                _client_browser.close()
            except Exception:
                pass
            _client_browser = None
            _browser_context = None
        if _browser_context:
            try:
                _browser_context.close()
            except Exception:
                pass
            _browser_context = None
        if _playwright_instance:
            try:
                _playwright_instance.stop()
            except Exception:
                pass
            _playwright_instance = None
        _client_instance = None


# ═══════════════════════════════════════════════════════════════════════════════
# URL parsing (same logic as xhs_fetcher.py)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_note_url(url: str) -> dict:
    """Parse XHS note URL into note_id, xsec_token, xsec_source."""
    parsed = urlparse(url)
    path_parts = parsed.path.rstrip("/").split("/")
    note_id = path_parts[-1] if path_parts else ""
    params = parse_qs(parsed.query)
    return {
        "note_id": note_id,
        "xsec_token": params.get("xsec_token", [""])[0],
        "xsec_source": params.get("xsec_source", ["pc_search"])[0],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Format conversion: MediaCrawler response → project standardized schema
# ═══════════════════════════════════════════════════════════════════════════════

def _format_note_card(note: dict, url: str) -> dict:
    """Convert MediaCrawler note_card to project's standardized output.

    MediaCrawler's get_note_by_id returns note_card dict with keys:
      note_id, title, desc, type, user, image_list, video, tag_list,
      interact_info (collected/liked/comment/share counts), time, ip_location
    """
    note_id = note.get("note_id", "")
    title = note.get("title", "") or note.get("display_title", "")
    desc = note.get("desc", "")
    user = note.get("user", {}) or {}
    nickname = user.get("nickname", "")
    user_id = user.get("user_id", "")

    interact = note.get("interact_info", {}) or {}
    liked = interact.get("liked_count", 0)
    collected = interact.get("collected_count", 0)
    commented = interact.get("comment_count", 0)
    shared = interact.get("share_count", 0)

    ip_location = note.get("ip_location", "")
    time_ms = note.get("time", 0)
    publish_time = ""
    if time_ms:
        from datetime import datetime
        try:
            publish_time = datetime.fromtimestamp(time_ms / 1000).strftime("%Y-%m-%d")
        except Exception:
            publish_time = str(time_ms)

    tags = []
    for t in note.get("tag_list", []) or []:
        if isinstance(t, dict) and t.get("name"):
            tags.append(t["name"])

    content_parts = [f"标题：{title}"]
    if desc:
        content_parts.append(f"\n正文：{desc[:1500]}")
    if tags:
        content_parts.append(f"\n标签：{' '.join('#' + t for t in tags)}")

    likes_int = int(liked) if str(liked).isdigit() else 0
    estimated_views = likes_int * 80 if likes_int > 0 else None

    return {
        "原文内容": "\n".join(content_parts),
        "来源平台": "小红书",
        "发布者类型": f"小红书用户: {nickname}" if nickname else f"小红书用户: {user_id}",
        "互动数据": f"点赞{liked}, 收藏{collected}, 评论{commented}, 分享{shared}",
        "发布时间": publish_time,
        "原文链接": url,
        "评论列表": [],
        "社媒数据": {
            "作者": nickname or user_id,
            "国家": ip_location,
            "点赞": likes_int,
            "评论": int(commented) if str(commented).isdigit() else 0,
            "粉丝": 0,
            "播放量": estimated_views,
            "作者主页": [f"https://www.xiaohongshu.com/user/profile/{user_id}"],
            "_播放量估算": True,
        },
        "_meta": {
            "note_id": note_id,
            "nickname": nickname,
            "source": "mediacrawler",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_xhs_note(url: str, max_comments: int = 10) -> dict:
    """Fetch XHS note detail + comments via MediaCrawler XiaoHongShuClient.

    Strategy (tried in order):
      1. get_note_by_id (API, needs valid cookies + xhshow signing)
      2. get_note_by_id_from_html with enable_cookie=False (guest HTML parse)
      3. get_note_by_id_from_html with enable_cookie=True (authenticated HTML)

    Guest HTML fallback (step 2) works even when the account is banned, because
    XHS allows public note pages without authentication.
    """
    parsed = _parse_note_url(url)
    note_id = parsed["note_id"]
    xsec_token = parsed["xsec_token"]
    xsec_source = parsed["xsec_source"]

    if not note_id:
        return _error("无法解析笔记ID", url, "Failed to parse note_id from URL")

    client = _get_client()
    if not client:
        return _error(
            "小红书未登录", url,
            "Cookie not found. Run: python -c \"from engine.xhs_fetcher import bootstrap_cookies; bootstrap_cookies(force=True)\"",
        )

    get_limiter("xhs").acquire()

    note = None
    last_error = ""

    # Step 1: API (needs valid cookies + xhshow signing)
    try:
        note = _run_async(client.get_note_by_id(note_id, xsec_source, xsec_token))
    except Exception as e:
        last_error = str(e)
        # Detect banned-account response
        if "300031" in last_error or "461" in last_error:
            last_error = "Cookie已失效(账号被封或登录过期)，请刷新登录"

    # Step 2: Guest HTML fallback (no cookies)
    if not note:
        try:
            note = _run_async(
                client.get_note_by_id_from_html(note_id, xsec_source, xsec_token, enable_cookie=False)
            )
        except Exception as e:
            err_str = str(e)
            # RetryError wrapping KeyError = note not found in page (guest blocked)
            if "KeyError" in err_str or "JSONDecodeError" in err_str:
                last_error = last_error or "Guest access blocked by XHS"
            else:
                last_error = last_error or err_str

    # Step 3: Authenticated HTML fallback (last resort)
    if not note:
        try:
            note = _run_async(
                client.get_note_by_id_from_html(note_id, xsec_source, xsec_token, enable_cookie=True)
            )
        except Exception as e:
            err_str = str(e)
            if "KeyError" in err_str or "JSONDecodeError" in err_str:
                last_error = last_error or "Note page HTML extraction failed (note may be deleted)"
            else:
                last_error = last_error or err_str

    if not note:
        return _error(
            "笔记不存在或无法访问" if not last_error else f"抓取失败: {last_error[:100]}",
            url,
            last_error or "Note not found or access denied",
        )

    result = _format_note_card(note, url)

    # Fetch comments (only if we have valid cookies — API-based)
    if client.cookie_dict:
        try:
            comments_raw = _run_async(
                client.get_note_comments(note_id, xsec_token, cursor="")
            )
            comments = []
            for c in (comments_raw.get("comments", []) if isinstance(comments_raw, dict) else comments_raw):
                if isinstance(c, dict):
                    text = c.get("content", "") or c.get("text", "")
                    like_count = c.get("like_count", "0")
                    if text:
                        comments.append({"内容": str(text).strip()[:300], "点赞": str(like_count)})
            result["评论列表"] = comments[:max_comments]
        except Exception:
            pass  # Comments are optional

    return result


def search_xhs(keyword: str, count: int = 30, sort_type: str = "date") -> List[dict]:
    """Search XHS by keyword via MediaCrawler XiaoHongShuClient.

    Args:
        keyword: Search keyword
        count: Max results (capped at XHS API limit of 20 per page)
        sort_type: 'date' (最新) or 'general' (综合)

    Returns:
        List of SearchResult-compatible dicts
    """
    client = _get_client()
    if not client:
        print("[MediaCrawler] Client not available for search — cookie missing.")
        return []

    get_limiter("xhs").acquire()

    sort = SearchSortType.LATEST if sort_type == "date" else SearchSortType.GENERAL
    search_id = get_search_id()

    import asyncio as _asyncio

    results = []
    page = 1
    max_pages = max(1, count // 20 + 1)

    while page <= max_pages:
        try:
            resp = _run_async(
                client.get_note_by_keyword(
                    keyword=keyword,
                    search_id=search_id,
                    page=page,
                    page_size=min(count, 20),
                    sort=sort,
                    note_type=SearchNoteType.ALL,
                )
            )
        except Exception as e:
            print(f"[MediaCrawler] Search error: {e}")
            break

        if not resp:
            break

        items = resp.get("items", [])
        if not items:
            break

        for item in items:
            if item.get("model_type") in ("rec_query", "hot_query"):
                continue
            note_card = item.get("note_card") or item
            results.append({
                "title": note_card.get("title", "") or note_card.get("display_title", ""),
                "url": f"https://www.xiaohongshu.com/explore/{item.get('id', '')}",
                "author": (note_card.get("user", {}) or {}).get("nickname", ""),
                "publish_time": "",
                "engagement": (note_card.get("interact_info", {}) or {}).get("liked_count", 0),
                "snippet": (note_card.get("desc", "") or "")[:200],
                "note_id": item.get("id", ""),
                "xsec_token": item.get("xsec_token", ""),
                "xsec_source": item.get("xsec_source", ""),
            })

        has_more = resp.get("has_more", False)
        page += 1
        if not has_more or len(results) >= count:
            break

    return results[:count]


def _error(prefix: str, url: str, detail: str) -> dict:
    return {
        "原文内容": f"[{prefix} - 请重试]",
        "来源平台": "小红书",
        "发布者类型": "未知",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
        "社媒数据": {
            "作者": "", "国家": "", "点赞": 0, "评论": 0,
            "粉丝": 0, "播放量": None, "作者主页": [],
        },
        "_scrape_error": detail,
    }


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else input("XHS note URL: ").strip()
    result = fetch_xhs_note(url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
