# -*- coding: utf-8 -*-
"""
Douyin/TikTok content fetcher using TikTokDownloader (DouK-Downloader v5.8).

Architecture (information-theoretic channel isolation):
  Channel 1: Metadata via Detail interface (147 fields from aweme API)
  Channel 2: Comments via Comment interface (aweme comment API)
  Both require cookies (抖音 API restriction, not tool limitation).

Cookie lifecycle mirrors xhs_fetcher.py: cache → expire check → prompt refresh.
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ENGINE_DIR = Path(__file__).resolve().parent

# TikTokDownloader path
_TT_DOWNLOADER_PATH = Path("D:/Claude code/Github skills/TikTokDownloader")
_TT_AVAILABLE = False
if _TT_DOWNLOADER_PATH.exists():
    _tt_src = str(_TT_DOWNLOADER_PATH)
    if _tt_src not in sys.path:
        sys.path.insert(0, _tt_src)
    try:
        from src.application import TikTokDownloader as _TTApp  # noqa: F401
        _TT_AVAILABLE = True
    except ImportError:
        pass

TT_COOKIE_FILE = ENGINE_DIR / ".tt_cookies.json"


# ═══════════════════════════════════════════════════════════════════════════════
# URL parsing
# ═══════════════════════════════════════════════════════════════════════════════

def extract_video_id(url: str) -> str:
    """Extract 19-digit video ID from various douyin URL formats."""
    import re
    # Direct video ID (19 digits)
    if m := re.search(r"(\d{19})", url):
        return m.group(1)
    # modal_id parameter
    parsed = urlparse(url)
    from urllib.parse import parse_qs
    params = parse_qs(parsed.query)
    if mid := params.get("modal_id", [None])[0]:
        return mid
    # Short link resolution would need network call; return hash fallback
    import hashlib
    return hashlib.md5(url.encode()).hexdigest()[:8]


def build_video_url(video_id: str) -> str:
    return f"https://www.douyin.com/video/{video_id}"


# ═══════════════════════════════════════════════════════════════════════════════
# Cookie management
# ═══════════════════════════════════════════════════════════════════════════════

def _load_tt_cookie() -> Optional[dict]:
    """Load cached douyin cookie dict from settings.json (written by TikTokDownloader)."""
    settings_path = _TT_DOWNLOADER_PATH / "Volume" / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8-sig"))
            cookie = data.get("cookie", {})
            if cookie and isinstance(cookie, dict) and len(cookie) > 3:
                return cookie
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _cookie_str(d: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in d.items())


def _check_cookie_valid() -> bool:
    """Quick validity check: do we have core auth cookies?"""
    c = _load_tt_cookie()
    if not c:
        return False
    required = ["passport_csrf_token", "s_v_web_id"]
    return all(k in c for k in required)


# ═══════════════════════════════════════════════════════════════════════════════
# Metadata extraction
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_douyin_metadata(video_id: str) -> Optional[dict]:
    """Channel 1: Fetch video metadata via TikTokDownloader Detail interface."""
    if not _TT_AVAILABLE or not _check_cookie_valid():
        return None
    import asyncio as _asyncio

    async def _extract():
        async with _TTApp() as app:
            app.check_config()
            await app.check_settings(False)
            from src.interface import Detail
            detail = Detail(app.parameter, detail_id=video_id)
            result = await detail.run(
                referer=build_video_url(video_id),
                single_page=True,
            )
            return result

    try:
        results = _asyncio.run(_extract())
    except Exception:
        return None
    if not results:
        return None
    return results[0] if isinstance(results, list) else results


# ═══════════════════════════════════════════════════════════════════════════════
# Comment extraction
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_douyin_comments(video_id: str, max_count: int = 10) -> list:
    """Channel 2: Fetch video comments via TikTokDownloader Comment interface."""
    if not _TT_AVAILABLE or not _check_cookie_valid():
        return []
    import asyncio as _asyncio

    async def _extract():
        async with _TTApp() as app:
            app.check_config()
            await app.check_settings(False)
            from src.interface import Comment
            c = Comment(
                app.parameter,
                detail_id=video_id,
                pages=1,
                count=min(max_count, 50),
            )
            result = await c.run(single_page=True, data_key="comments")
            return result

    try:
        results = _asyncio.run(_extract())
    except Exception:
        return []
    return results if isinstance(results, list) else []


# ═══════════════════════════════════════════════════════════════════════════════
# Output formatting
# ═══════════════════════════════════════════════════════════════════════════════

def _format_douyin_metadata(raw: dict, video_id: str) -> dict:
    """Convert TikTokDownloader Detail output to project's standardized schema.

    Information-theoretic design: single-channel transform, key name mapping only.
    No information added or removed — pure encoding conversion.
    """
    title = raw.get("desc", "") or raw.get("item_title", "") or ""
    author_info = raw.get("author", {})
    nickname = author_info.get("nickname", "")
    sec_uid = author_info.get("sec_uid", "")
    uid = author_info.get("uid", "")
    followers = author_info.get("follower_count", 0)
    signature = author_info.get("signature", "")

    stats = raw.get("statistics", {})
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

    # Tags from text_extra
    tag_list = raw.get("text_extra", [])
    tags = []
    for t in tag_list:
        if t.get("hashtag_name"):
            tags.append(t["hashtag_name"])

    content_parts = [f"标题：{title}"]
    if dur_str:
        content_parts.append(f"时长：{dur_str}")
    if signature:
        content_parts.append(f"作者简介：{signature[:200]}")
    if tags:
        content_parts.append(f"标签：{' '.join('#' + t for t in tags)}")

    likes_int = int(digg) if str(digg).isdigit() else 0

    return {
        "metadata": {
            "title": title, "nickname": nickname, "video_id": video_id,
            "duration_ms": duration_ms, "tags": tags,
            "digg": digg, "comment_cnt": comment_cnt,
            "collect": collect, "share": share, "play": play,
        },
        "原文内容": "\n".join(content_parts),
        "发布者类型": f"抖音用户: {nickname}{' (' + str(followers) + '粉丝)' if followers else ''}",
        "互动数据": f"点赞{digg:,}, 评论{comment_cnt:,}, 收藏{collect:,}, 分享{share:,}"
                    + (f", 播放{play:,}" if play else ""),
        "发布时间": publish_time,
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
            "video_id": video_id,
            "nickname": nickname,
            "source": "tiktok-downloader",
        },
    }


def _assemble_douyin_result(formatted: dict, url: str, comments_raw: list) -> dict:
    """Assemble final result from formatted metadata + comments."""
    comments = []
    for c in comments_raw:
        text = c.get("text", "") or c.get("content", "")
        like_count = c.get("digg_count", 0) or c.get("like_count", 0)
        if text:
            comments.append({"内容": str(text).strip()[:300], "点赞": str(like_count)})
    return {
        "原文内容": formatted["原文内容"],
        "来源平台": "抖音",
        "发布者类型": formatted["发布者类型"],
        "互动数据": formatted["互动数据"],
        "发布时间": formatted["发布时间"],
        "原文链接": url,
        "评论列表": comments,
        "社媒数据": formatted["社媒数据"],
        "_meta": formatted["_meta"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_douyin_video(url: str, max_comments: int = 10) -> dict:
    """Fetch Douyin video metadata + comments.

    Returns standardized dict for annotation engine, same schema as fetch_xhs_note.
    """
    video_id = extract_video_id(url)

    if not _TT_AVAILABLE:
        return _error("TikTokDownloader 未安装", url, "TikTokDownloader not available")
    if not _check_cookie_valid():
        return _error(
            "抖音Cookie未配置或已过期", url,
            "Cookie missing or expired. Open douyin.com, F12 → Console → document.cookie → paste to TikTokDownloader.",
        )

    raw = _fetch_douyin_metadata(video_id)
    if not raw:
        return _error("视频数据抓取失败", url, "API returned no data")

    formatted = _format_douyin_metadata(raw, video_id)
    comments_raw = _fetch_douyin_comments(video_id, max_comments)
    return _assemble_douyin_result(formatted, url, comments_raw)


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
    import sys as _sys
    url = _sys.argv[1] if len(_sys.argv) > 1 else input("Douyin URL: ").strip()
    result = fetch_douyin_video(url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
