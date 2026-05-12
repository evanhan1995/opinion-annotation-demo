"""舆情内容抓取器 —— 多平台内容 + 评论区抓取。

支持平台: YouTube (yt-dlp), 小红书 (xhshow API), X/Twitter, Reddit, 通用网页

用法:
    from scraper import scrape
    result = scrape("https://www.youtube.com/watch?v=xxx")
    result = scrape("https://www.xiaohongshu.com/explore/xxx")
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Windows terminal UTF-8 adaptation
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


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

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "getcomments": True,
        "extract_flat": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

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

    # Build content
    content_parts = [f"标题：{title}"]
    if description:
        content_parts.append(f"\n描述：{description[:1000]}")

    result["原文内容"] = "\n".join(content_parts)
    result["发布者类型"] = f"YouTuber: {channel}{sub_str}"
    result["互动数据"] = f"播放{views:,}, 点赞{likes:,}, 评论{comment_count:,}"
    result["发布时间"] = upload_date
    result["评论列表"] = comments

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# XHS (小红书): xhshow algorithm + httpx API
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_xhs(url: str, timeout: int = 30000) -> dict:
    """Scrape XHS note detail + comments using xhshow API client."""
    from engine.xhs_fetcher import fetch_xhs_note
    return fetch_xhs_note(url)


# ═══════════════════════════════════════════════════════════════════════════════
# Reddit: Playwright-based scraping
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_reddit(url: str, timeout: int = 30000) -> dict:
    """Scrape Reddit post (using old.reddit.com)."""
    from playwright.sync_api import sync_playwright

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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page.goto(old_url, timeout=timeout, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

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

        browser.close()

    result["原文内容"] = f"标题：{title}\n\n正文：{body[:1000] if body else '(无正文)'}"
    result["发布者类型"] = f"Reddit用户: {author}"
    result["互动数据"] = f"upvote {score}, {comment_count}"
    result["发布时间"] = post_time

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# X/Twitter: Playwright-based scraping
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_x(url: str, timeout: int = 30000) -> dict:
    """Scrape X/Twitter post."""
    from playwright.sync_api import sync_playwright

    result = {
        "原文内容": "",
        "来源平台": "X (Twitter)",
        "发布者类型": "",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

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

        browser.close()

    result["原文内容"] = tweet_text[:1000]
    result["发布者类型"] = f"X用户: {author}"
    result["互动数据"] = f"回复{replies}, 转发{retweets}, 点赞{likes}, 查看{views}"
    result["发布时间"] = post_time

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Generic web page
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_generic(url: str, timeout: int = 30000) -> dict:
    """Generic web page scraper."""
    from playwright.sync_api import sync_playwright

    result = {
        "原文内容": "",
        "来源平台": "通用网页",
        "发布者类型": "未知",
        "互动数据": "",
        "发布时间": "",
        "原文链接": url,
        "评论列表": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        title = page.title() or ""
        body = ""
        for selector in ["article", "main", "div.post-content", "div.content", "body"]:
            el = page.query_selector(selector)
            if el:
                body = el.inner_text()
                if len(body) > 100:
                    break

        browser.close()

    result["原文内容"] = f"标题：{title}\n\n正文：{body[:1500] if body else '(无法提取正文)'}"
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Scraper dispatch table
# ═══════════════════════════════════════════════════════════════════════════════

SCRAPERS = {
    "YouTube": _scrape_youtube,
    "小红书": _scrape_xhs,
    "Reddit": _scrape_reddit,
    "X": _scrape_x,
}


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
