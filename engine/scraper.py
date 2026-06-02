"""舆情内容抓取器 —— 多平台内容 + 评论区抓取。

支持平台: YouTube (yt-dlp), 小红书 (xhshow API), 抖音, B站 (bilibili-api),
         微博 (crawl4weibo), 微信公众号 (wechatarticles), X/Twitter, Reddit, 通用网页

用法:
    from scraper import scrape
    result = scrape("https://www.youtube.com/watch?v=xxx")
    result = scrape("https://www.xiaohongshu.com/explore/xxx")
"""

import io
import json
import re
import sys
import time
import hashlib
from concurrent import futures
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse

# Hard timeout for yt-dlp extract_info calls (seconds).
_SCRAPE_TIMEOUT = 90
_DEFAULT_RETRIES = 2
_DEFAULT_RETRY_BASE_DELAY = 2.0

import engine._compat

ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
RAW_CASES_DIR = PROJECT_DIR / "raw" / "cases"

PLATFORM_ABBREV = {
    "小红书": "xhs",
    "YouTube": "ytb",
    "X": "x",
    "X (Twitter)": "x",
    "Reddit": "reddit",
    "Instagram": "ig",
    "TikTok": "tt",
    "抖音": "dy",
    "B站": "bl",
    "微博": "wb",
    "微信公众号": "wc",
    "通用网页": "web",
    "新闻媒体": "news",
    "论坛": "forum",
    "其他": "other",
}


def _extract_content_id(url: str, platform: str) -> str:
    """Extract stable content ID from URL for file naming. Falls back to MD5 hash."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    path_parts = path.split("/")

    if platform in ("小红书", "抖音", "微博"):
        return path_parts[-1] if path_parts else hashlib.md5(url.encode()).hexdigest()[:8]

    if platform == "B站":
        # Extract BV/AV number from bilibili URL
        import re
        m = re.search(r'/(BV[a-zA-Z0-9]{10}|av\d+)', url)
        if m:
            return m.group(1)
        return path_parts[-1] if path_parts else hashlib.md5(url.encode()).hexdigest()[:8]

    if platform == "微信公众号":
        # Extract __biz + sn from query params
        from urllib.parse import parse_qs
        qs = parse_qs(parsed.query)
        biz = qs.get("__biz", [""])[0][:16] if qs.get("__biz") else ""
        sn = qs.get("sn", [""])[0][:8] if qs.get("sn") else ""
        if biz:
            return biz[-8:] + (sn or "")
        return hashlib.md5(url.encode()).hexdigest()[:8]

    if platform == "YouTube":
        from urllib.parse import parse_qs
        params = parse_qs(parsed.query)
        video_id = params.get("v", [None])[0]
        if video_id:
            return video_id
        if "youtu.be" in parsed.netloc:
            return path.lstrip("/").split("?")[0]
        return hashlib.md5(url.encode()).hexdigest()[:8]

    if platform in ("X", "X (Twitter)"):
        return path_parts[-1] if len(path_parts) >= 2 else hashlib.md5(url.encode()).hexdigest()[:8]

    if platform == "Reddit" and "comments" in path_parts:
        idx = path_parts.index("comments")
        if idx + 1 < len(path_parts):
            return path_parts[idx + 1]

    return hashlib.md5(url.encode()).hexdigest()[:8]


def _write_raw_cases(data: dict, url: str, platform: str) -> str | None:
    """Write scraped data to raw/cases/YYYY-MM-DD_{platform}_{id}.json. Returns filename or None."""
    today = date.today().isoformat()
    content_id = _extract_content_id(url, platform)
    abbrev = PLATFORM_ABBREV.get(platform, "web")
    filename = f"{today}_{abbrev}_{content_id}.json"
    RAW_CASES_DIR.mkdir(parents=True, exist_ok=True)
    filepath = RAW_CASES_DIR / filename
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filename
    except OSError:
        return None


def _get_config() -> dict:
    """Load engine/config.json. Returns empty dict on failure."""
    config_path = ENGINE_DIR / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _with_retry(fn, *args, max_retries=None, base_delay=None, _url="", _platform="", _stage=""):
    """Execute fn(*args) with exponential backoff retry. Delegates to engine.retry."""
    from engine.retry import retry_call, RetryConfig
    if max_retries is None:
        max_retries = _DEFAULT_RETRIES
    if base_delay is None:
        base_delay = _DEFAULT_RETRY_BASE_DELAY
    return retry_call(fn, *args,
                      config=RetryConfig(max_retries=max_retries, base_delay=base_delay),
                      _url=_url, _platform=_platform, _stage=_stage)


def _detect_platform(url: str) -> str:
    """Auto-detect platform from URL."""
    domain = urlparse(url).netloc.lower()
    if "youtube.com" in domain or "youtu.be" in domain:
        return "YouTube"
    if "xiaohongshu.com" in domain or "rednote.com" in domain:
        return "小红书"
    if "x.com" in domain or "twitter.com" in domain:
        return "X"
    if "reddit.com" in domain:
        return "Reddit"
    if "instagram.com" in domain:
        return "Instagram"
    if "tiktok.com" in domain:
        return "TikTok"
    if "douyin.com" in domain:
        return "抖音"
    if "bilibili.com" in domain:
        return "B站"
    if "weibo.com" in domain:
        return "微博"
    if "mp.weixin.qq.com" in domain or "weixin.sogou.com" in domain:
        return "微信公众号"
    if "instagram.com" in domain:
        return "Instagram"
    if "tiktok.com" in domain:
        return "TikTok"
    return "通用网页"


# ═══════════════════════════════════════════════════════════════════════════════
# YouTube: yt-dlp based (fast, reliable, no browser needed)
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_youtube(url: str, timeout: int = 30000) -> dict:
    """Scrape YouTube video metadata + comments using yt-dlp."""
    import yt_dlp

    result = {
        "原文内容": "",
        "来源平台": "YouTube",
        "发布者类型": "",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
    }

    cfg = _get_config()
    youtube_cfg = cfg.get("youtube", {})
    _scrape_timeout = youtube_cfg.get("scrape_timeout", _SCRAPE_TIMEOUT)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "getcomments": True,
        "extract_flat": False,
        "extractor_args": {"youtube": {"max_comments": ["10"]}},
        "socket_timeout": 60,
    }

    # Cookie support for age-restricted / member-only videos
    cookie_file = youtube_cfg.get("cookie_file", "")
    if cookie_file and Path(cookie_file).exists():
        ydl_opts["cookiefile"] = cookie_file

    info = {}  # Initialize before with-block to prevent NameError on early failure

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            executor = futures.ThreadPoolExecutor(max_workers=1)
            try:
                fut = executor.submit(ydl.extract_info, url, False)
                try:
                    return fut.result(timeout=_scrape_timeout)
                except futures.TimeoutError:
                    result["原文内容"] = f"[抓取超时: yt-dlp 在 {_scrape_timeout}s 内未返回]"
                    return None
                except Exception as exc:
                    result["原文内容"] = f"[抓取失败: {exc}]"
                    return None
            finally:
                executor.shutdown(wait=False)

    try:
        info = _with_retry(
            _extract, max_retries=2, base_delay=2.0,
            _platform="YouTube", _stage="extract_info",
        )
    except Exception as exc:
        result["原文内容"] = f"[抓取失败(已重试): {exc}]"
        return result

    if info is None:
        return result  # Error message already set in _extract

    title = info.get("title", "")
    channel = info.get("channel", "")
    description = info.get("description", "") or ""

    views = info.get("view_count") or 0
    likes = info.get("like_count") or 0
    comment_count = info.get("comment_count") or 0
    duration = info.get("duration") or 0
    upload_date = info.get("upload_date", "")

    # Format date
    if upload_date and len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

    # Subscriber count
    channel_follower_count = info.get("channel_follower_count", 0) or 0
    sub_str = f", {channel_follower_count:,}订阅" if channel_follower_count else ""

    # Comments
    raw_comments = info.get("comments", [])[:10]
    comments = []
    for c in raw_comments:
        text = c.get("text", "")
        likes_c = c.get("like_count", 0) or 0
        if text:
            comments.append({"内容": text.strip()[:500], "点赞": str(likes_c)})

    # Format duration
    mins, secs = divmod(duration or 0, 60)
    hours, mins = divmod(mins, 60)
    dur_str = f"{hours}时{mins}分{secs}秒" if hours else f"{mins}分{secs}秒" if mins else f"{secs}秒"

    # Build content (full description for LLM context)
    content_parts = [f"标题：{title}"]
    if description:
        content_parts.append(f"\n描述：{description[:2000]}")
    content_parts.append(f"\n时长：{dur_str}")

    result["原文内容"] = "\n".join(content_parts)
    result["发布者类型"] = f"YouTuber: {channel}{sub_str}"
    result["互动数据"] = f"播放{views:,}, 点赞{likes:,}, 评论{comment_count:,}"
    result["发布时间"] = upload_date
    result["评论列表"] = comments
    result["社媒数据"] = {
        "作者": channel,
        "国家": "",
        "点赞": likes,
        "评论": comment_count,
        "粉丝": channel_follower_count,
        "播放量": views,
        "时长": dur_str,
        "作者主页": [f"https://www.youtube.com/@{channel.replace(' ', '')}" if channel else ""],
    }

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# XHS (小红书): xhshow algorithm + httpx API
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_xhs(url: str, timeout: int = 30000) -> dict:
    """Scrape XHS note detail + comments.

    Tiered strategy (lightest first):
      1. XHS-Downloader (cookie-free metadata) → xhshow API
      2. MediaCrawler adapter (API → guest HTML → auth HTML fallback)
    """
    from engine.xhs_fetcher import fetch_xhs_note as _fetch_via_xhshow

    result = _fetch_via_xhshow(url)
    if not result.get("_scrape_error"):
        return result

    # Tier 1 failed — try MediaCrawler adapter (adds HTML parsing fallback)
    try:
        from engine.mediacrawler_adapter import fetch_xhs_note as _fetch_via_mc
        mc_result = _fetch_via_mc(url)
        if not mc_result.get("_scrape_error"):
            return mc_result
    except ImportError:
        pass

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Reddit: Playwright-based scraping
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_reddit_json_api(url: str) -> dict:
    """Scrape Reddit post via JSON API (no browser, more reliable). Returns None on failure."""
    import requests as _requests
    json_url = url.rstrip("/") + ".json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = _requests.get(json_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        post_data = data[0]["data"]["children"][0]["data"]
    except Exception:
        return None

    title = post_data.get("title", "")
    body = post_data.get("selftext", "")
    author = post_data.get("author", "")
    score = post_data.get("score", 0)
    comment_count = post_data.get("num_comments", 0)
    created_utc = post_data.get("created_utc", 0)
    from datetime import datetime
    post_time = datetime.fromtimestamp(created_utc).isoformat() if created_utc else ""
    permalink = post_data.get("permalink", "")

    # Top-level comments
    comments = []
    try:
        comment_data = data[1]["data"]["children"]
        for c in comment_data[:10]:
            cdata = c.get("data", {})
            body_text = cdata.get("body", "")
            c_score = cdata.get("score", 0)
            if body_text.strip():
                comments.append({"内容": body_text.strip()[:300], "点赞": str(c_score)})
    except Exception:
        pass

    return {
        "原文内容": f"标题：{title}\n\n正文：{body[:1000] if body else '(无正文)'}",
        "来源平台": "Reddit",
        "发布者类型": f"Reddit用户: {author}",
        "互动数据": f"upvote {score}, {comment_count} 评论",
        "发布时间": post_time,
        "原文链接": url,
        "评论列表": comments,
        "社媒数据": {"作者": author, "国家": "", "点赞": score,
                      "评论": comment_count, "粉丝": 0,
                      "播放量": None, "作者主页": []},
    }


def _scrape_reddit_playwright(url: str, timeout: int = 30000) -> dict:
    """Fallback: scrape Reddit post via old.reddit.com + Playwright."""
    from engine.browser_pool import launch_context

    old_url = re.sub(r'(://)?(www\.)?reddit\.com', r'\1old.reddit.com', url)

    result = {
        "原文内容": "",
        "来源平台": "Reddit",
        "发布者类型": "",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
    }

    ctx, browser, pw = launch_context(
        headless=True, stealth=False,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )
    try:
        page = ctx.new_page()
        page.goto(old_url, timeout=timeout, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("a.title", timeout=5000)
        except Exception:
            pass

        title_el = page.query_selector("a.title")
        title = title_el.inner_text() if title_el else ""

        body_el = page.query_selector("div.expando div.md, div.usertext-body div.md")
        body = body_el.inner_text() if body_el else ""

        author_el = page.query_selector("a.author")
        author = author_el.inner_text() if author_el else ""

        score_el = page.query_selector("div.score.unvoted")
        score = score_el.get_attribute("title") if score_el else ""
        if not score:
            score_text = score_el.inner_text() if score_el else ""
            score = score_text

        comment_count_el = page.query_selector("a.comments")
        comment_count = comment_count_el.inner_text() if comment_count_el else ""

        time_el = page.query_selector("time")
        post_time = time_el.get_attribute("datetime") if time_el else ""

        comment_els = page.query_selector_all("div.comment div.entry")
        for i, c in enumerate(comment_els[:10]):
            try:
                text_el = c.query_selector("div.md")
                text = text_el.inner_text() if text_el else ""
                score_el_c = c.query_selector("span.score")
                cl = score_el_c.inner_text() if score_el_c else ""
                if text.strip():
                    result["评论列表"].append({"内容": text.strip()[:300], "点赞": cl})
            except Exception:
                continue
    finally:
        browser.close()
        pw.stop()

    result["原文内容"] = f"标题：{title}\n\n正文：{body[:1000] if body else '(无正文)'}"
    result["发布者类型"] = f"Reddit用户: {author}"
    result["互动数据"] = f"upvote {score}, {comment_count}"
    result["发布时间"] = post_time
    result["社媒数据"] = {"作者": author, "国家": "", "点赞": _parse_int(score),
                          "评论": _parse_int(comment_count), "粉丝": 0,
                          "播放量": None, "作者主页": []}

    return result


def _scrape_reddit(url: str, timeout: int = 30000) -> dict:
    """Scrape Reddit post: try JSON API first, fallback to Playwright."""
    result = _scrape_reddit_json_api(url)
    if result and result.get("原文内容") and "标题：" in result["原文内容"]:
        return result
    return _scrape_reddit_playwright(url, timeout)


# ═══════════════════════════════════════════════════════════════════════════════
# Generic helpers

def _parse_int(s: str) -> int:
    """Parse a string to int, handling '1.2k' like formats. Returns 0 on failure."""
    if not s:
        return 0
    s = str(s).strip().lower().replace(",", "")
    try:
        return int(float(s))
    except ValueError:
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# X/Twitter: Playwright-based scraping
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_x(url: str, timeout: int = 30000) -> dict:
    """Scrape X/Twitter post."""
    from engine.browser_pool import launch_context

    result = {
        "原文内容": "",
        "来源平台": "X (Twitter)",
        "发布者类型": "",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
    }

    cfg = _get_config()
    x_cfg = cfg.get("x", {})

    ctx, browser, pw = launch_context(
        headless=True, stealth=False,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )
    try:
        # Inject auth_token cookie if configured
        auth_token = x_cfg.get("auth_token", "")
        if auth_token:
            try:
                ctx.add_cookies([{
                    "name": "auth_token", "value": auth_token,
                    "domain": ".x.com", "path": "/",
                }])
            except Exception:
                pass

        page = ctx.new_page()
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("article[data-testid='tweet']", timeout=8000)
        except Exception:
            pass

        tweet_el = page.query_selector("article div[data-testid='tweetText']")
        tweet_text = tweet_el.inner_text() if tweet_el else ""

        author_el = page.query_selector("div[data-testid='User-Name'] a")
        author = author_el.inner_text() if author_el else ""

        reply_el = page.query_selector("button[data-testid='reply'] span")
        replies = reply_el.inner_text() if reply_el else "0"

        retweet_el = page.query_selector("button[data-testid='retweet'] span")
        retweets = retweet_el.inner_text() if retweet_el else "0"

        like_el = page.query_selector("button[data-testid='like'] span")
        likes = like_el.inner_text() if like_el else "0"

        view_el = page.query_selector("a[href$='/analytics'] span")
        if not view_el:
            view_el = page.query_selector("span[data-testid='app-text-transition-container']")
        views = view_el.inner_text() if view_el else ""

        time_el = page.query_selector("time")
        post_time = time_el.get_attribute("datetime") if time_el else ""

        reply_els = page.query_selector_all("article[data-testid='tweet']")
        for i, r in enumerate(reply_els[1:11]):
            try:
                text_el = r.query_selector("div[data-testid='tweetText']")
                text = text_el.inner_text() if text_el else ""
                if text.strip():
                    result["评论列表"].append({"内容": text.strip()[:300], "点赞": "0"})
            except Exception:
                continue
    finally:
        browser.close()
        pw.stop()

    result["原文内容"] = tweet_text[:1000]
    result["发布者类型"] = f"X用户: {author}"
    result["互动数据"] = f"回复{replies}, 转发{retweets}, 点赞{likes}, 查看{views}"
    result["发布时间"] = post_time
    result["社媒数据"] = {"作者": author, "国家": "", "点赞": _parse_int(likes),
                          "评论": _parse_int(replies), "粉丝": 0,
                          "播放量": _parse_int(views), "作者主页": []}

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Generic web page
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_generic(url: str, timeout: int = 30000) -> dict:
    """Generic web page scraper."""
    from engine.browser_pool import launch_context

    result = {
        "原文内容": "",
        "来源平台": "通用网页",
        "发布者类型": "未知",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
    }

    ctx, browser, pw = launch_context(
        headless=True, stealth=False,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )
    try:
        page = ctx.new_page()
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("article, main, div.post-content, div.content", timeout=5000)
        except Exception:
            page.wait_for_timeout(1000)

        title = page.title() or ""
        body = ""
        _selectors = [
            "article", "main", "div.post-content", "div.content",
            "div.article-content", "div.entry-content", "div#content",
            "div.content-wrapper", "body",
        ]
        for selector in _selectors:
            el = page.query_selector(selector)
            if el:
                body = el.inner_text()
                if len(body) > 100:
                    break

        # Fallback: meta description
        if not body or len(body) < 50:
            meta_el = page.query_selector("meta[name='description'], meta[property='og:description']")
            if meta_el:
                meta_content = meta_el.get_attribute("content")
                if meta_content:
                    body = meta_content
    finally:
        browser.close()
        pw.stop()

    result["原文内容"] = f"标题：{title}\n\n正文：{body[:1500] if body else '(无法提取正文)'}"
    result["社媒数据"] = {"作者": "", "国家": "", "点赞": 0, "评论": 0,
                          "粉丝": 0, "播放量": None, "作者主页": []}
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Scraper dispatch table
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# Douyin (抖音): TikTokDownloader-based (cookie-free metadata, cookie for comments)
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_douyin(url: str, timeout: int = 30000) -> dict:
    """Scrape douyin video via TikTokDownloader, with MediaCrawler fallback."""
    from engine.tt_fetcher import fetch_douyin_video
    result = fetch_douyin_video(url)
    if not result.get("_scrape_error"):
        return result
    # Fallback: try MediaCrawler DouYinClient
    try:
        from engine.douyin_adapter import fetch_douyin_note
        mc_result = fetch_douyin_note(url)
        if not mc_result.get("_scrape_error"):
            return mc_result
    except ImportError:
        pass
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# B站 (Bilibili): bilibili-api-python — async API, wrapped in sync helper
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_bilibili(url: str, timeout: int = 30000) -> dict:
    """Scrape B站 video via bilibili-api-python."""
    import asyncio as _asyncio
    vid = _extract_content_id(url, "B站")

    cfg = _get_config()
    bl_cfg = cfg.get("bilibili", {})

    async def _fetch():
        from bilibili_api import video, Credential
        credential = Credential(
            sessdata=bl_cfg.get("sessdata", ""),
            bili_jct=bl_cfg.get("bili_jct", ""),
            buvid3=bl_cfg.get("buvid3", ""),
            dedeuserid=bl_cfg.get("dedeuserid", ""),
        )
        v = video.Video(bvid=vid if vid.startswith("BV") else None,
                        aid=int(vid[2:]) if vid.startswith("av") else None,
                        credential=credential)
        info = await v.get_info()
        stat = info.get("stat", {})
        owner = info.get("owner", {})

        # Get comments (top 10)
        comments = []
        try:
            from bilibili_api import comment
            c_data = await comment.get_comments(v.get_aid(), comment.CommentResourceType.VIDEO, page_index=1)
            for c in c_data.get("replies", [])[:10]:
                comments.append(c.get("content", {}).get("message", "") or "")
        except Exception as e:
            print(f"[B站] Comment fetch failed: {e}", file=sys.stderr)

        return info, stat, owner, comments

    try:
        info, stat, owner, comments = _asyncio.run(_fetch())
    except Exception as e:
        return {
            "原文内容": f"(B站抓取失败: {e})",
            "发布时间": "",
            "来源平台": "B站",
            "发布者类型": "未知",
            "互动数据": "",
            "原文链接": url,
            "社媒数据": {"作者": "", "国家": "CN", "点赞": 0, "评论": 0, "粉丝": 0, "播放量": None, "作者主页": []},
            "评论列表": [],
        }

    desc = info.get("desc", "")
    title = info.get("title", "")
    content = f"标题：{title}\n\n{desc}"
    pub_ts = info.get("pubdate", 0)
    publish_time = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else ""

    author_name = owner.get("name", "")
    author_mid = owner.get("mid", "")
    homepage = f"https://space.bilibili.com/{author_mid}" if author_mid else ""

    return {
        "原文内容": content[:3000],
        "发布时间": publish_time,
        "来源平台": "B站",
        "发布者类型": f"B站UP主: {author_name}" if author_name else "未知",
        "互动数据": "",
        "原文链接": url,
        "社媒数据": {
            "作者": author_name,
            "国家": "CN",
            "点赞": stat.get("like", 0) or 0,
            "评论": stat.get("reply", 0) or 0,
            "粉丝": 0,
            "播放量": stat.get("view", 0) or 0,
            "作者主页": [homepage] if homepage else [],
        },
        "评论列表": comments[:10],
    }




def _scrape_weibo(url: str, timeout: int = 30000) -> dict:
    """Scrape 微博 post via crawl4weibo."""
    bid = _extract_content_id(url, "微博")
    try:
        from crawl4weibo import WeiboClient
        client = WeiboClient()
        post = client.get_post_by_bid(bid)

        author_name = ""
        followers_str = "0"
        homepage = ""
        try:
            user = client.get_user_by_uid(post.user_id)
            author_name = user.screen_name or ""
            followers_str = str(user.followers_count) if user.followers_count else "0"
            homepage = f"https://weibo.com/u/{post.user_id}" if post.user_id else ""
        except Exception as e:
            print(f"[微博] User info fetch failed: {e}", file=sys.stderr)

        comments_list = []
        try:
            comments, _ = client.get_comments(post.id, page=1)
            for c in comments[:10]:
                if c.text:
                    comments_list.append(c.text.strip())
        except Exception as e:
            print(f"[微博] Comment fetch failed: {e}", file=sys.stderr)

        pub_ts = str(post.created_at) if post.created_at else ""
        if pub_ts and "+" in pub_ts:
            pub_ts = pub_ts.split("+")[0].strip()

        return {
            "原文内容": post.text[:3000] if post.text else "",
            "发布时间": pub_ts,
            "来源平台": "微博",
            "发布者类型": f"微博用户: {author_name}" if author_name else "未知",
            "互动数据": "",
            "原文链接": url,
            "社媒数据": {
                "作者": author_name,
                "国家": "CN",
                "点赞": post.attitudes_count or 0,
                "评论": post.comments_count or 0,
                "粉丝": followers_str,
                "播放量": None,
                "作者主页": [homepage] if homepage else [],
            },
            "评论列表": comments_list[:10],
        }
    except Exception as e:
        return {
            "原文内容": f"(微博抓取失败: {e})",
            "发布时间": "",
            "来源平台": "微博",
            "发布者类型": "未知",
            "互动数据": "",
            "原文链接": url,
            "社媒数据": {"作者": "", "国家": "CN", "点赞": 0, "评论": 0, "粉丝": 0, "播放量": None, "作者主页": []},
            "评论列表": [],
        }


def _scrape_wechat(url: str, timeout: int = 30000) -> dict:
    """Scrape 微信公众号 article — public page parsing via requests + BeautifulSoup."""
    import requests as _requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    try:
        resp = _requests.get(url, headers=headers, timeout=min(timeout / 1000, 30))
        if resp.status_code != 200:
            return {
                "原文内容": f"(微信公众号抓取失败: HTTP {resp.status_code})",
                "发布时间": "", "来源平台": "微信公众号", "发布者类型": "未知",
                "互动数据": "", "原文链接": url,
                "社媒数据": {"作者": "", "国家": "CN", "点赞": 0, "评论": 0, "粉丝": 0, "播放量": None, "作者主页": []},
                "评论列表": [],
            }
        html = resp.text
    except Exception as e:
        return {
            "原文内容": f"(微信公众号抓取失败: {e})",
            "发布时间": "", "来源平台": "微信公众号", "发布者类型": "未知",
            "互动数据": "", "原文链接": url,
            "社媒数据": {"作者": "", "国家": "CN", "点赞": 0, "评论": 0, "粉丝": 0, "播放量": None, "作者主页": []},
            "评论列表": [],
        }

    from bs4 import BeautifulSoup as _bs
    soup = _bs(html, "lxml")

    # Title: og:title meta or h2#activity-name
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content", "")
    if not title:
        h2_title = soup.find("h2", id="activity-name")
        if h2_title:
            title = h2_title.get_text(strip=True)
    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

    # Author (公众号名称): og:article:author meta or span#js_name
    author = ""
    og_author = soup.find("meta", property="og:article:author")
    if og_author:
        author = og_author.get("content", "")
    if not author:
        js_name = soup.find(id="js_name")
        if js_name:
            author = js_name.get_text(strip=True)

    # Publish time
    publish_time = ""
    og_time = soup.find("meta", property="og:article:published_time")
    if og_time:
        publish_time = og_time.get("content", "")[:19]
    if not publish_time:
        pub_em = soup.find("em", id="publish_time")
        if pub_em:
            publish_time = pub_em.get_text(strip=True)
    # Try to parse timestamp from page scripts
    if not publish_time:
        import re
        ts_match = re.search(r'var\s+ct\s*=\s*["\'](\d{10,13})["\']', html)
        if ts_match:
            try:
                ts = int(ts_match.group(1))
                if ts > 1e12:
                    ts = ts / 1000.0
                from datetime import datetime
                publish_time = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

    # Content: div#js_content.rich_media_content
    content = ""
    js_content = soup.find("div", id="js_content")
    if js_content:
        # Remove hidden elements
        for hidden in js_content.select(".rich_media_area_extra, script, style"):
            hidden.decompose()
        content = js_content.get_text(separator="\n", strip=True)

    if not content:
        # Try alternative: rich_media_content class
        rm_content = soup.find("div", class_="rich_media_content")
        if rm_content:
            content = rm_content.get_text(separator="\n", strip=True)

    return {
        "原文内容": content[:3000] if content else f"标题：{title}",
        "发布时间": publish_time,
        "来源平台": "微信公众号",
        "发布者类型": f"公众号: {author}" if author else "未知",
        "互动数据": "",
        "原文链接": url,
        "社媒数据": {
            "作者": author,
            "国家": "CN",
            "点赞": 0,
            "评论": 0,
            "粉丝": 0,
            "播放量": None,
            "作者主页": [],
        },
        "评论列表": [],
    }


def _scrape_instagram(url: str, timeout: int = 30000) -> dict:
    """Instagram: not supported due to aggressive anti-scraping. Returns clear error."""
    return {
        "原文内容": "(Instagram 暂不支持自动抓取，请手动粘贴帖子内容或截图)",
        "来源平台": "Instagram",
        "发布者类型": "未知",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
        "社媒数据": {"作者": "", "国家": "", "点赞": 0, "评论": 0, "粉丝": 0, "播放量": None, "作者主页": []},
    }


def _scrape_tiktok(url: str, timeout: int = 30000) -> dict:
    """TikTok: requires mobile API tokens not available in pipeline. Returns clear error."""
    return {
        "原文内容": "(TikTok 暂不支持自动抓取，请手动粘贴帖子内容或截图)",
        "来源平台": "TikTok",
        "发布者类型": "未知",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
        "社媒数据": {"作者": "", "国家": "", "点赞": 0, "评论": 0, "粉丝": 0, "播放量": None, "作者主页": []},
    }


SCRAPERS = {
    "YouTube": _scrape_youtube,
    "小红书": _scrape_xhs,
    "Reddit": _scrape_reddit,
    "X": _scrape_x,
    "抖音": _scrape_douyin,
    "B站": _scrape_bilibili,
    "微博": _scrape_weibo,
    "微信公众号": _scrape_wechat,
    "Instagram": _scrape_instagram,
    "TikTok": _scrape_tiktok,
}


def fetch_youtube_subtitles(url: str) -> str:
    """Fetch auto-captions / subtitles from a YouTube video. Returns text or empty string."""
    import json as _json
    from urllib.request import urlopen
    import yt_dlp
    ydl_opts = {
        "quiet": True, "no_warnings": True, "extract_flat": False,
        "writesubtitles": True, "writeautomaticsub": True,
        "subtitleslangs": ["zh-Hans", "zh", "en"],
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    subs = info.get("subtitles") or info.get("automatic_captions") or {}
    for lang in ("zh-Hans", "zh", "en"):
        for e in subs.get(lang, []):
            if e.get("ext") in ("json3", "srv1", "srv2", "srv3"):
                try:
                    resp = urlopen(e["url"], timeout=15)
                    events = _json.loads(resp.read()).get("events", [])
                    lines = []
                    for ev in events[:500]:
                        for seg in ev.get("segs", []):
                            t = seg.get("utf8", "").strip()
                            if t and t not in ("\n", "[音乐]", "[Music]", "[掌声]", "[Applause]"):
                                lines.append(t)
                    return " ".join(lines)
                except Exception:
                    pass
    return ""


def scrape(url: str, timeout: int = 30000) -> dict:
    """Auto-detect platform and scrape content.

    Args:
        url: Target URL
        timeout: Timeout in milliseconds (for Playwright-based scrapers)

    Returns:
        dict: Standardized sentiment input data
    """
    platform = _detect_platform(url)
    scraper = SCRAPERS.get(platform, _scrape_generic)

    try:
        result = scraper(url, timeout)
        result["来源平台"] = platform
        _write_raw_cases(result, url, platform)
        return result
    except Exception as e:
        return {
            "原文内容": f"[抓取失败: {e}]",
            "来源平台": platform,
            "发布者类型": "未知",
            "互动数据": "",
            "发布时间": "",
            "原文链接": url,
            "评论列表": [],
            "_scrape_error": str(e),
        }


if __name__ == "__main__":
    import sys as _sys
    url = _sys.argv[1] if len(_sys.argv) > 1 else "https://www.youtube.com/watch?v=3A8G5PznsOg"
    print(f"Scraping: {url}")
    result = scrape(url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
