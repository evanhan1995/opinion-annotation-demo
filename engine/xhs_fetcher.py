# -*- coding: utf-8 -*-
"""
XHS (Xiaohongshu / REDnote) note fetcher using xhshow pure-algorithm signing.

Requires: pip install xhshow httpx
Cookie bootstrap uses Playwright sync API (consistent with scraper.py).

Architecture:
  - xhshow library generates API signatures from cookies (no browser needed)
  - Cookies are bootstrapped once via Playwright, then cached to file
  - Subsequent calls use cached cookies + httpx API calls
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, quote

# Windows UTF-8 adaptation
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import httpx

# xhshow is installed via pip (MediaCrawler dependency)
from xhshow import Xhshow

ENGINE_DIR = Path(__file__).resolve().parent
COOKIE_FILE = ENGINE_DIR / ".xhs_cookies.json"

API_HOST = "https://edith.xiaohongshu.com"
WEB_HOST = "https://www.xiaohongshu.com"


# ═══════════════════════════════════════════════════════════════════════════════
# URL parsing
# ═══════════════════════════════════════════════════════════════════════════════

def parse_note_url(url: str) -> dict:
    """Parse XHS note URL into note_id, xsec_token, xsec_source."""
    parsed = urlparse(url)
    path_parts = parsed.path.rstrip("/").split("/")
    note_id = path_parts[-1] if path_parts else ""
    # Extract query params
    from urllib.parse import parse_qs
    params = parse_qs(parsed.query)
    return {
        "note_id": note_id,
        "xsec_token": params.get("xsec_token", [""])[0],
        "xsec_source": params.get("xsec_source", ["pc_search"])[0],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Cookie Management
# ═══════════════════════════════════════════════════════════════════════════════

def _load_cached_cookies() -> Optional[str]:
    """Load cookie string from cache file."""
    if COOKIE_FILE.exists():
        try:
            data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
            ts = data.get("saved_at", 0)
            # Cache valid for 7 days
            if time.time() - ts < 7 * 24 * 3600:
                return data.get("cookie_str", "")
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _save_cookies(cookie_str: str) -> None:
    """Save cookie string to cache file."""
    COOKIE_FILE.write_text(
        json.dumps({"cookie_str": cookie_str, "saved_at": time.time()}, ensure_ascii=False),
        encoding="utf-8",
    )


def bootstrap_cookies(force: bool = False) -> Optional[str]:
    """Use Playwright to get XHS cookies from browser.

    Tries cached cookies first. If expired/missing, opens a browser
    (reusing MediaCrawler's cached profile if available) and extracts cookies.

    Returns:
        Cookie string on success, None on failure.
    """
    if not force:
        cached = _load_cached_cookies()
        if cached:
            return cached

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[XHS] Playwright not available, cannot bootstrap cookies.")
        return None

    # Try MediaCrawler's cached profile
    media_crawler_profile = Path("D:/Claude code/MediaCrawler/browser_data/xhs_user_data_dir")

    with sync_playwright() as p:
        if media_crawler_profile.exists():
            browser_context = p.chromium.launch_persistent_context(
                user_data_dir=str(media_crawler_profile),
                headless=False,
                viewport={"width": 1920, "height": 1080},
            )
        else:
            browser = p.chromium.launch(headless=False)
            browser_context = browser.new_context(viewport={"width": 1920, "height": 1080})

        page = browser_context.new_page()
        page.goto(WEB_HOST, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Check login state
        try:
            page.wait_for_selector("xpath=//a[contains(@href, '/user/profile/')]//span[text()='我']",
                                   timeout=10000)
            print("[XHS] Login detected via cached profile.")
        except Exception:
            print("[XHS] Not logged in. Please scan QR code in the browser window...")
            print("[XHS] Waiting up to 120 seconds for login...")
            try:
                page.wait_for_selector(
                    "xpath=//a[contains(@href, '/user/profile/')]//span[text()='我']",
                    timeout=120000,
                )
                print("[XHS] Login successful!")
            except Exception:
                print("[XHS] Login timeout. Please run MediaCrawler once to login first.")
                browser_context.close()
                return None

        # Extract cookies
        cookies = browser_context.cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        browser_context.close()

        _save_cookies(cookie_str)
        return cookie_str


def get_cookie_string(allow_bootstrap: bool = True) -> Optional[str]:
    """Get XHS cookie string from cache. Auto-bootstraps if cache is empty."""
    cookie = _load_cached_cookies()
    if not cookie and allow_bootstrap:
        cookie = bootstrap_cookies()
    return cookie


# ═══════════════════════════════════════════════════════════════════════════════
# XHS API Client (xhshow-based, no browser needed after cookies are cached)
# ═══════════════════════════════════════════════════════════════════════════════

class XhsApiClient:
    """Lightweight XHS API client using xhshow for signing."""

    def __init__(self, cookie_str: str):
        self.cookie_str = cookie_str
        self.xhshow = Xhshow()
        self.client = httpx.Client(timeout=30)

    def _sign_headers(self, uri: str, data: dict, method: str = "POST") -> dict:
        """Generate signed headers via xhshow standard API (unified GET/POST)."""
        if method.upper() == "POST":
            return self.xhshow.sign_headers(
                method="POST", uri=uri, cookies=self.cookie_str, payload=data,
            )
        else:
            return self.xhshow.sign_headers(
                method="GET", uri=uri, cookies=self.cookie_str, params=data,
            )

    def _get(self, uri: str, params: dict) -> dict:
        headers = self._sign_headers(uri, params, "GET")
        headers["Cookie"] = self.cookie_str
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        headers["Referer"] = f"{WEB_HOST}/"

        # Build URL with proper encoding
        if params:
            parts = []
            for k, v in params.items():
                vs = str(v) if v is not None else ""
                parts.append(f"{k}={quote(vs, safe=',')}")
            full_url = f"{API_HOST}{uri}?{'&'.join(parts)}"
        else:
            full_url = f"{API_HOST}{uri}"

        resp = self.client.get(full_url, headers=headers)
        data = resp.json()
        if data.get("success"):
            return data.get("data", {})
        msg = data.get("msg", "")
        if "登录" in msg or "login" in msg.lower() or data.get("code") == -100:
            raise Exception("XHS_COOKIE_EXPIRED")
        raise Exception(f"XHS API error: {msg or resp.text[:200]}")

    def _post(self, uri: str, payload: dict) -> dict:
        headers = self._sign_headers(uri, payload, "POST")
        headers["Cookie"] = self.cookie_str
        headers["Content-Type"] = "application/json;charset=UTF-8"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        headers["Referer"] = f"{WEB_HOST}/"
        headers["Origin"] = WEB_HOST

        json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        resp = self.client.post(f"{API_HOST}{uri}", content=json_str, headers=headers)
        data = resp.json()
        if data.get("success"):
            return data.get("data", {})
        code = data.get("code", 0)
        msg = data.get("msg", "")
        if "登录" in msg or "login" in msg.lower() or code == -100:
            raise Exception("XHS_COOKIE_EXPIRED")
        if code in (-510000, -510001):
            raise Exception(f"Note not found or abnormal (code: {code})")
        raise Exception(f"XHS API error: {msg or resp.text[:200]}")

    def get_note_detail(self, note_id: str, xsec_token: str, xsec_source: str = "pc_search") -> dict:
        """Fetch note detail by note_id."""
        if not xsec_source:
            xsec_source = "pc_search"
        payload = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
            "xsec_source": xsec_source,
            "xsec_token": xsec_token,
        }
        res = self._post("/api/sns/web/v1/feed", payload)
        if res and res.get("items"):
            return res["items"][0]["note_card"]
        return {}

    def get_note_comments(self, note_id: str, xsec_token: str, max_count: int = 10) -> List[dict]:
        """Fetch comments for a note."""
        comments = []
        cursor = ""
        while len(comments) < max_count:
            params = {
                "note_id": note_id,
                "cursor": cursor,
                "top_comment_id": "",
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token,
            }
            res = self._get("/api/sns/web/v2/comment/page", params)
            has_more = res.get("has_more", False)
            cursor = res.get("cursor", "")
            batch = res.get("comments", [])
            if not batch:
                break
            comments.extend(batch)
            if not has_more:
                break
        return comments[:max_count]

    def close(self):
        self.client.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_xhs_note(url: str, max_comments: int = 10) -> dict:
    """Fetch XHS note detail + comments. Returns standardized dict for annotation engine.

    Args:
        url: XHS note URL (must contain xsec_token)
        max_comments: Maximum number of comments to fetch

    Returns:
        dict with keys: 原文内容, 来源平台, 发布者类型, 互动数据, 发布时间, 原文链接, 评论列表
    """
    # Parse URL
    parsed = parse_note_url(url)
    note_id = parsed["note_id"]
    xsec_token = parsed["xsec_token"]
    xsec_source = parsed["xsec_source"]

    # Get cookies (auto-bootstrap if cache is empty)
    cookie_str = get_cookie_string(allow_bootstrap=True)
    if not cookie_str:
        return {
            "原文内容": "[小红书登录未完成 - 请在弹出的浏览器窗口中扫码登录]",
            "来源平台": "小红书",
            "发布者类型": "",
            "互动数据": "",
            "发布时间": "",
            "原文链接": url,
            "评论列表": [],
            "_scrape_error": "Login required. A browser window should open for QR code scanning. If not, click '刷新小红书登录' in sidebar.",
        }

    # Fetch data
    client = XhsApiClient(cookie_str)
    try:
        note = client.get_note_detail(note_id, xsec_token, xsec_source)
        comments_raw = client.get_note_comments(note_id, xsec_token, max_comments)
    except Exception as e:
        err_msg = str(e)
        if "XHS_COOKIE_EXPIRED" in err_msg:
            # Delete expired cookie, bootstrap fresh, retry once
            if COOKIE_FILE.exists():
                COOKIE_FILE.unlink()
            cookie_str = bootstrap_cookies(force=True)
            if cookie_str:
                client.close()
                client = XhsApiClient(cookie_str)
                try:
                    note = client.get_note_detail(note_id, xsec_token, xsec_source)
                    comments_raw = client.get_note_comments(note_id, xsec_token, max_comments)
                except Exception as e2:
                    err_msg2 = str(e2)
                    return {
                        "原文内容": f"[抓取失败: {err_msg2}]\n\n请尝试在侧边栏点击'刷新小红书登录'后重试。",
                        "来源平台": "小红书",
                        "发布者类型": "未知",
                        "互动数据": "",
                        "发布时间": "",
                        "原文链接": url,
                        "评论列表": [],
                        "_scrape_error": err_msg2,
                    }
            else:
                return {
                    "原文内容": "[小红书Cookie已过期 - 请在弹出的浏览器窗口中扫码登录后重试]",
                    "来源平台": "小红书",
                    "发布者类型": "",
                    "互动数据": "",
                    "发布时间": "",
                    "原文链接": url,
                    "评论列表": [],
                    "_scrape_error": "Cookie expired and re-login failed. Try clicking '刷新小红书登录' in sidebar.",
                }
        return {
            "原文内容": f"[抓取失败: {err_msg}]",
            "来源平台": "小红书",
            "发布者类型": "未知",
            "互动数据": "",
            "发布时间": "",
            "原文链接": url,
            "评论列表": [],
            "_scrape_error": err_msg,
        }
    finally:
        client.close()

    if not note:
        return {
            "原文内容": f"[抓取失败: 笔记不存在或无法访问]",
            "来源平台": "小红书",
            "发布者类型": "未知",
            "互动数据": "",
            "发布时间": "",
            "原文链接": url,
            "评论列表": [],
            "_scrape_error": "Note not found or access denied",
        }

    # Extract fields
    title = note.get("title", "") or note.get("display_title", "")
    desc = note.get("desc", "")
    user = note.get("user", {})
    nickname = user.get("nickname", "")
    user_id = user.get("user_id", "")
    # XHS note detail API may include follower count; keys vary by API version
    followers = (
        user.get("follower_count") or user.get("followers") or
        user.get("fans") or user.get("fans_count") or 0
    )

    interact = note.get("interact_info", {})
    liked = interact.get("liked_count", "0")
    collected = interact.get("collected_count", "0")
    commented = interact.get("comment_count", "0")
    shared = interact.get("share_count", "0")

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
    tag_list = note.get("tag_list", [])
    if tag_list:
        for t in tag_list:
            tags.append(t.get("name", ""))

    # Build content
    content_parts = [f"标题：{title}"]
    if desc:
        content_parts.append(f"\n正文：{desc[:1500]}")
    if tags:
        content_parts.append(f"\n标签：{' '.join(['#' + t for t in tags])}")

    # Build comments
    comments = []
    for c in comments_raw:
        text = c.get("content", "")
        like_count = c.get("like_count", "0")
        if text:
            comments.append({"内容": text.strip(), "点赞": str(like_count)})

    likes_int = int(liked) if str(liked).isdigit() else 0
    estimated_views = likes_int * 80 if likes_int > 0 else None
    return {
        "原文内容": "\n".join(content_parts),
        "来源平台": "小红书",
        "发布者类型": f"小红书用户: {nickname} ({user_id})" if nickname else f"小红书用户: {user_id}",
        "互动数据": f"点赞{liked}, 收藏{collected}, 评论{commented}, 分享{shared}",
        "发布时间": publish_time,
        "原文链接": url,
        "评论列表": comments,
        "社媒数据": {
            "作者": nickname or user_id,
            "国家": ip_location,
            "点赞": likes_int,
            "评论": int(commented) if str(commented).isdigit() else 0,
            "粉丝": int(followers) if str(followers).isdigit() else (followers if isinstance(followers, int) else 0),
            "播放量": estimated_views,
            "作者主页": [f"https://www.xiaohongshu.com/user/profile/{user_id}"],
            "_播放量估算": True,
        },
        "_meta": {
            "note_id": note_id,
            "nickname": nickname,
            "ip_location": ip_location,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entry point for testing
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys as _sys
    url = _sys.argv[1] if len(_sys.argv) > 1 else input("XHS note URL: ").strip()
    result = fetch_xhs_note(url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
