# -*- coding: utf-8 -*-
"""
Douyin adapter — wraps MediaCrawler DouYinClient for in-process douyin search + detail.

Uses MediaCrawler's Playwright-based browser approach. The key difference from
TikTokDownloader (pure HTTP): search endpoint skips a_bogus signature, and
msToken is read from localStorage.xmst — both require a real browser context.

Architecture:
  Existing douyin cookies (tt_fetcher.py bootstrap) → settings.json
      → douyin_adapter.py loads cookies → launch Playwright browser
          → DouYinClient for search (no a_bogus) + detail/comment API

Usage:
    from engine.douyin_adapter import search_douyin, fetch_douyin_note
    results = search_douyin("Temu", count=10)
    note = fetch_douyin_note("https://www.douyin.com/video/xxx")
"""

import asyncio as _asyncio
import concurrent.futures
import io
import json
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional

import engine._compat

ENGINE_DIR = Path(__file__).resolve().parent
_MEDIACRAWLER_PATH = Path("D:/Claude code/MediaCrawler")
if _MEDIACRAWLER_PATH.exists() and str(_MEDIACRAWLER_PATH) not in sys.path:
    sys.path.insert(0, str(_MEDIACRAWLER_PATH))

from engine.browser_pool import BROWSER_ARGS as _BROWSER_ARGS, STEALTH_JS as _STEALTH_JS
_MC_STEALTH_JS = _MEDIACRAWLER_PATH / "libs" / "stealth.min.js"

_client_lock = threading.RLock()
_client_instance = None
_event_loop = None
_loop_thread = None


def _get_or_create_event_loop() -> _asyncio.AbstractEventLoop:
    """Get or create a background event loop for Playwright async operations."""
    global _event_loop, _loop_thread
    with _client_lock:
        if _event_loop is not None and not _event_loop.is_closed():
            return _event_loop
        _event_loop = _asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_event_loop.run_forever, daemon=True)
        _loop_thread.start()
        return _event_loop


def _run_async(coro):
    """Run an async coroutine on the background event loop, return result."""
    loop = _get_or_create_event_loop()
    future = _asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=120)


# ═══════════════════════════════════════════════════════════════════════════════
# Cookie loading — shared with tt_fetcher.py via TikTokDownloader settings.json
# ═══════════════════════════════════════════════════════════════════════════════

def _load_tt_settings() -> Optional[dict]:
    settings_path = Path("D:/Claude code/Github skills/TikTokDownloader/Volume/settings.json")
    if not settings_path.exists():
        return None
    try:
        return json.loads(settings_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, KeyError):
        return None


def _load_cookie_dict() -> Optional[Dict[str, str]]:
    data = _load_tt_settings()
    if not data:
        return None
    cookie = data.get("cookie", {})
    if isinstance(cookie, dict) and len(cookie) > 3:
        return cookie
    return None


def _load_cookie_str() -> Optional[str]:
    data = _load_tt_settings()
    if not data:
        return None
    cookie = data.get("cookie", {})
    if isinstance(cookie, dict) and cookie:
        return "; ".join(f"{k}={v}" for k, v in cookie.items())
    return None


def _check_cookie_valid() -> bool:
    c = _load_cookie_dict()
    if not c:
        return False
    session_keys = ["sessionid_ss", "sid_guard", "sessionid"]
    return any(k in c for k in session_keys)


# ═══════════════════════════════════════════════════════════════════════════════
# Client singleton
# ═══════════════════════════════════════════════════════════════════════════════

def _get_client():
    global _client_instance

    cookie_dict = _load_cookie_dict()
    cookie_str = _load_cookie_str()
    if not cookie_dict or not cookie_str:
        return None

    if _client_instance is not None:
        return _client_instance

    async def _init():
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=_BROWSER_ARGS)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )

        stealth_js = _STEALTH_JS if _STEALTH_JS.exists() else _MC_STEALTH_JS
        if stealth_js.exists():
            await ctx.add_init_script(path=str(stealth_js))

        page = await ctx.new_page()
        await page.goto("https://www.douyin.com", timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Inject cookies
        pw_cookies = [{"name": k, "value": str(v), "domain": ".douyin.com", "path": "/"}
                      for k, v in cookie_dict.items()]
        await ctx.add_cookies(pw_cookies)

        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json;charset=UTF-8",
            "Host": "www.douyin.com",
            "Origin": "https://www.douyin.com",
            "Pragma": "no-cache",
            "Referer": "https://www.douyin.com/",
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
            "Cookie": cookie_str,
        }

        # MediaCrawler modules use relative paths (e.g. 'libs/douyin.js')
        import os as _os
        _prev_cwd = _os.getcwd()
        _os.chdir(str(_MEDIACRAWLER_PATH))
        try:
            from media_platform.douyin.client import DouYinClient
        finally:
            _os.chdir(_prev_cwd)

        return DouYinClient(
            headers=headers,
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

    with _client_lock:
        if _client_instance is not None:
            return _client_instance
        _client_instance = _run_async(_init())
        return _client_instance


def _cleanup_client():
    global _client_instance, _event_loop
    with _client_lock:
        _client_instance = None
        if _event_loop and not _event_loop.is_closed():
            _event_loop.call_soon_threadsafe(_event_loop.stop)


# ═══════════════════════════════════════════════════════════════════════════════
# URL parsing
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_video_id(url: str) -> str:
    import re
    if m := re.search(r"(\d{19})", url):
        return m.group(1)
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if mid := params.get("modal_id", [None])[0]:
        return mid
    import hashlib
    return hashlib.md5(url.encode()).hexdigest()[:8]


# ═══════════════════════════════════════════════════════════════════════════════
# Format conversion: MediaCrawler search → SearchResult-compatible dict
# ═══════════════════════════════════════════════════════════════════════════════

def _format_search_item(item: dict) -> dict:
    """Convert MediaCrawler search item to SearchResult-compatible dict."""
    aweme_info = item.get("aweme_info", item)
    author = aweme_info.get("author", {}) or {}
    statistics = aweme_info.get("statistics", {}) or {}
    return {
        "title": aweme_info.get("desc", "") or aweme_info.get("title", ""),
        "url": f"https://www.douyin.com/video/{aweme_info.get('aweme_id', '')}",
        "author": author.get("nickname", ""),
        "publish_time": str(aweme_info.get("create_time", "")),
        "engagement": statistics.get("digg_count", 0),
        "snippet": (aweme_info.get("desc", "") or "")[:200],
        "note_id": aweme_info.get("aweme_id", ""),
        "aweme_id": aweme_info.get("aweme_id", ""),
    }


def _format_douyin_note(raw: dict, url: str) -> dict:
    """Convert MediaCrawler get_video_by_id response to project standardized schema."""
    title = raw.get("desc", "") or raw.get("item_title", "") or ""
    author_info = raw.get("author", {}) or {}
    nickname = author_info.get("nickname", "")
    sec_uid = author_info.get("sec_uid", "")
    followers = author_info.get("follower_count", 0)

    stats = raw.get("statistics", {}) or {}
    digg = stats.get("digg_count", 0)
    comment_cnt = stats.get("comment_count", 0)
    collect = stats.get("collect_count", 0)
    share = stats.get("share_count", 0)
    play = stats.get("play_count", 0)

    duration_ms = raw.get("duration", 0)
    mins, secs = divmod(duration_ms // 1000, 60)
    hours, mins = divmod(mins, 60)
    dur_str = f"{hours}时{mins}分{secs}秒" if hours else f"{mins}分{secs}秒"

    from datetime import datetime
    create_ts = raw.get("create_time", 0)
    publish_time = ""
    if create_ts:
        try:
            publish_time = datetime.fromtimestamp(create_ts).strftime("%Y-%m-%d")
        except Exception:
            publish_time = str(create_ts)

    tag_list = raw.get("text_extra", []) or []
    tags = [t["hashtag_name"] for t in tag_list if t.get("hashtag_name")]

    signature = author_info.get("signature", "")
    content_parts = [f"标题：{title}"]
    if dur_str:
        content_parts.append(f"时长：{dur_str}")
    if signature:
        content_parts.append(f"作者简介：{signature[:200]}")
    if tags:
        content_parts.append(f"标签：{' '.join('#' + t for t in tags)}")

    likes_int = int(digg) if str(digg).isdigit() else 0

    return {
        "原文内容": "\n".join(content_parts),
        "来源平台": "抖音",
        "发布者类型": f"抖音用户: {nickname}{' (' + str(followers) + '粉丝)' if followers else ''}",
        "互动数据": f"点赞{digg:,}, 评论{comment_cnt:,}, 收藏{collect:,}, 分享{share:,}"
                    + (f", 播放{play:,}" if play else ""),
        "发布时间": publish_time,
        "原文链接": url,
        "评论列表": [],
        "社媒数据": {
            "作者": nickname,
            "国家": "",
            "点赞": likes_int,
            "评论": int(comment_cnt) if str(comment_cnt).isdigit() else 0,
            "粉丝": int(followers) if str(followers).isdigit() else 0,
            "播放量": int(play) if str(play).isdigit() else None,
            "作者主页": [f"https://www.douyin.com/user/{sec_uid}" if sec_uid else ""],
        },
        "_meta": {
            "video_id": raw.get("aweme_id", ""),
            "nickname": nickname,
            "source": "mediacrawler-douyin",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Browser-based search (response interception)
# ═══════════════════════════════════════════════════════════════════════════════

def _search_via_browser(keyword: str, count: int = 30, sort_type: str = "date") -> List[dict]:
    """Search Douyin by navigating to the search page and intercepting API responses.

    Douyin's search API returns verify_check for standalone HTTP requests.
    But the same API call made from a real browser page passes anti-bot checks.
    We navigate to the search page, capture XHR responses, and scroll to load more.
    """
    import urllib.parse
    from playwright.async_api import async_playwright

    cookie_dict = _load_cookie_dict()

    async def _do_search():
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(headless=True, args=_BROWSER_ARGS)
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/139.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )

            stealth_js = _STEALTH_JS if _STEALTH_JS.exists() else _MC_STEALTH_JS
            if stealth_js.exists():
                await ctx.add_init_script(path=str(stealth_js))

            if cookie_dict:
                pw_cookies = [{"name": k, "value": str(v), "domain": ".douyin.com", "path": "/"}
                              for k, v in cookie_dict.items()]
                await ctx.add_cookies(pw_cookies)

            page = await ctx.new_page()

            # Capture ALL API responses (initial load + scroll-triggered)
            captured_data = []

            async def _on_response(response):
                if "/aweme/v1/web/general/search/single/" in response.url:
                    try:
                        j = await response.json()
                        captured_data.append(j)
                    except Exception:
                        pass

            page.on("response", _on_response)

            sort_param = "0" if sort_type in ("hot", "general") else "2"
            search_url = (
                f"https://www.douyin.com/search/{urllib.parse.quote(keyword)}"
                f"?type=general&sort_type={sort_param}"
            )
            await page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(6000)

            # Scroll to load more results until we have enough
            max_scrolls = max(1, (count + 9) // 10)  # ~10 items per API call
            for _ in range(max_scrolls):
                prev_total = sum(len(d.get("data", []) or []) for d in captured_data)
                # Douyin uses a virtual scroll container, not document.body.
                # Try keyboard End + mouse wheel for reliable scroll trigger.
                await page.keyboard.press("End")
                await page.wait_for_timeout(1500)
                await page.mouse.wheel(0, 3000)
                await page.wait_for_timeout(2500)
                new_total = sum(len(d.get("data", []) or []) for d in captured_data)
                if new_total <= prev_total:
                    break  # No more results loaded

            if captured_data:
                # Merge all captured responses, dedup by aweme_id
                seen = set()
                results = []
                for resp_data in captured_data:
                    for item in (resp_data.get("data", []) or []):
                        aweme_info = item.get("aweme_info", item)
                        aid = aweme_info.get("aweme_id", "")
                        if aid and aid not in seen:
                            seen.add(aid)
                            results.append(_format_search_item(item))
                return results[:count]

            # Fallback: scrape DOM
            cards = await page.evaluate("""() => {
                const cards = document.querySelectorAll('.search-result-card');
                return Array.from(cards).slice(0, 20).map(card => {
                    const text = (card.textContent || '').trim();
                    const img = card.querySelector('img');
                    const imgSrc = img ? (img.getAttribute('src') || '') : '';
                    return { text, imgSrc };
                });
            }""")

            results = []
            for card in cards:
                text = card.get("text", "")
                if len(text) < 10:
                    continue
                results.append({
                    "title": text[:200],
                    "url": "",
                    "author": "",
                    "publish_time": "",
                    "engagement": 0,
                    "snippet": text[:200],
                    "note_id": "",
                })

            return results[:count]

        finally:
            try:
                await ctx.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass
            await pw.stop()

    return _run_async(_do_search())


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def search_douyin(keyword: str, count: int = 30, sort_type: str = "date") -> List[dict]:
    """Search Douyin by keyword.

    Tier 1: Browser-based search (Playwright → intercept API response from page).
             The page's own API call passes Douyin's anti-bot checks.
    Tier 2: MediaCrawler DouYinClient direct API (fallback).

    Args:
        keyword: Search keyword
        count: Max results
        sort_type: 'date' (最新) or 'general' (综合)

    Returns:
        List of SearchResult-compatible dicts
    """
    # Tier 1: Browser-based search with response interception
    try:
        results = _search_via_browser(keyword, count=count, sort_type=sort_type)
        if results:
            return results
    except Exception as e:
        print(f"[DouyinAdapter] Browser search error: {e}")

    # Tier 2: MediaCrawler DouYinClient direct API (fallback)
    client = _get_client()
    if not client:
        return []

    from media_platform.douyin.field import SearchChannelType, SearchSortType, PublishTimeType
    from media_platform.douyin.help import get_web_id

    sort = SearchSortType.LATEST if sort_type == "date" else SearchSortType.GENERAL
    search_id = get_web_id()

    results = []
    offset = 0
    max_pages = max(1, count // 15 + 1)

    while offset < count and (offset // 15) < max_pages:
        try:
            resp = _run_async(client.search_info_by_keyword(
                keyword=keyword,
                offset=offset,
                search_channel=SearchChannelType.GENERAL,
                sort_type=sort,
                publish_time=PublishTimeType.UNLIMITED,
                search_id=search_id,
            ))
        except Exception as e:
            print(f"[DouyinAdapter] Search error: {e}")
            break

        if not resp:
            break

        data = resp.get("data", []) or []
        if not data:
            break

        for item in data:
            results.append(_format_search_item(item))

        has_more = resp.get("has_more", 0) or resp.get("hasMore", 0)
        offset += len(data)
        if not has_more:
            break

    return results[:count]


def fetch_douyin_note(url: str, max_comments: int = 10) -> dict:
    """Fetch Douyin video detail + comments via MediaCrawler DouYinClient.

    Used as fallback when TikTokDownloader's detail fetch fails.
    """
    video_id = _extract_video_id(url)
    if not video_id or len(video_id) < 15:
        return _error("无法解析视频ID", url, "Failed to parse video_id from URL")

    client = _get_client()
    if not client:
        return _error(
            "抖音Cookie未配置", url,
            "Cookie not found. Run bootstrap_douyin_cookies() first.",
        )

    # Step 1: Detail
    try:
        note = _run_async(client.get_video_by_id(video_id))
    except Exception as e:
        return _error("视频数据抓取失败", url, str(e)[:200])

    if not note or not isinstance(note, dict):
        return _error("视频不存在或无法访问", url, "Empty response from API")

    # Check if video is private/under review
    if note.get("filter_reason"):
        return _error("视频被过滤", url, f"filter_reason: {note.get('filter_reason', '')}")

    result = _format_douyin_note(note, url)

    # Step 2: Comments
    try:
        comments_raw = _run_async(client.get_aweme_comments(video_id, cursor=0))
        comments = []
        comment_list = comments_raw.get("comments", []) if isinstance(comments_raw, dict) else []
        for c in (comment_list or []):
            if isinstance(c, dict):
                text = c.get("text", "") or c.get("content", "")
                like_count = c.get("digg_count", 0) or c.get("like_count", 0)
                if text:
                    comments.append({"内容": str(text).strip()[:300], "点赞": str(like_count)})
        result["评论列表"] = comments[:max_comments]
    except Exception:
        pass

    return result


def _error(prefix: str, url: str, detail: str) -> dict:
    return {
        "原文内容": f"[{prefix}]",
        "来源平台": "抖音",
        "发布者类型": "未知",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
        "社媒数据": {"作者": "", "国家": "", "点赞": 0, "评论": 0, "粉丝": 0,
                      "播放量": None, "作者主页": []},
        "_meta": {"video_id": "", "nickname": "", "source": "error"},
        "_scrape_error": detail,
    }


if __name__ == "__main__":
    # Quick test: search
    print("=== Douyin Search Test ===")
    results = search_douyin("Temu", count=5)
    print(f"Got {len(results)} results")
    for r in results[:3]:
        print(f"  - {r.get('title', '')[:60]}")
    if not results:
        print("  (no results — cookie may be expired)")
    print()
    print("=== Douyin Detail Test ===")
    note = fetch_douyin_note("https://www.douyin.com/video/7645336397187943722")
    print(f"  title: {note.get('原文内容', '')[:100]}")
    print(f"  error: {note.get('_scrape_error', 'none')}")
