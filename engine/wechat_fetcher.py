# -*- coding: utf-8 -*-
"""
WeChat (微信公众号) article search + fetch.

Search: Playwright + stealth.js → weixin.sogou.com (public, no login needed)
Fetch:  requests + BeautifulSoup → mp.weixin.qq.com (public article pages)

Architecture:
  search_wechat_articles(keyword) → Sogou WeChat search → article URL list
  fetch_wechat_article(url) → requests + BS4 → standardized dict
"""

import io
import sys
import re
import time
import threading
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

import engine._compat

ENGINE_DIR = Path(__file__).resolve().parent
from engine.browser_pool import launch_context, BROWSER_ARGS


# ═══════════════════════════════════════════════════════════════════════════════
# Search: Sogou WeChat (public, no credentials)
# ═══════════════════════════════════════════════════════════════════════════════

_EXTRACT_JS = """() => {
    const results = [];
    document.querySelectorAll('.news-list li').forEach(li => {
        const link = li.querySelector('a[href^="/link?url="]');
        if (!link) return;
        let ts = 0;
        const scripts = li.querySelectorAll('script');
        scripts.forEach(s => {
            const m = (s.textContent || '').match(/timeConvert\\('(\\d+)'\\)/);
            if (m) ts = parseInt(m[1], 10);
        });
        const authorEl = li.querySelector('.all-time-y2');
        const author = authorEl ? (authorEl.textContent || '').trim() : '';
        const h3 = li.querySelector('h3');
        const titleLink = h3 ? h3.querySelector('a') : link;
        const title = titleLink ? (titleLink.textContent || '').trim() : '';
        const snippetEl = li.querySelector('.s-p, .txt-info, p');
        const snippet = snippetEl ? (snippetEl.textContent || '').trim() : '';
        results.push({
            url: link.href, title: title, author: author, ts: ts, snippet: snippet
        });
    });
    return results;
}"""


def _process_raw_items(page, raw_items: list) -> list:
    """Convert JS-extracted items to result dicts with resolved URLs."""
    results = []
    for item in raw_items:
        title = item.get("title", "").strip()
        if not (title and len(title) > 3):
            continue

        sogou_url = item.get("url", "")
        if sogou_url.startswith("/"):
            sogou_url = "https://weixin.sogou.com" + sogou_url

        ts = item.get("ts", 0)
        publish_time = ""
        if ts > 0:
            try:
                from datetime import datetime as _dt
                publish_time = _dt.fromtimestamp(ts).strftime("%Y-%m-%d")
            except Exception:
                publish_time = str(ts)

        real_url = _resolve_sogou_url(page, sogou_url)

        results.append({
            "title": title[:200],
            "url": real_url,
            "author": item.get("author", ""),
            "publish_time": publish_time,
            "snippet": item.get("snippet", "")[:200],
            "_ts": ts,
        })
    return results


def search_wechat_articles(keyword: str, count: int = 20, sort_type: str = "hot") -> List[dict]:
    """Search WeChat articles via weixin.sogou.com with pagination.

    Uses Playwright with stealth.js to avoid anti-bot detection.
    No credentials needed — public Sogou search.

    Args:
        keyword: Search keyword
        count: Max results to return
        sort_type: "hot" (relevance) or "date" (client-side sort by publish timestamp)

    Returns list of {title, url, author, publish_time, snippet}.
    URLs are resolved to real mp.weixin.qq.com addresses.
    """
    ctx, browser, pw = launch_context(headless=True, stealth=True)
    page = ctx.new_page()

    results = []
    max_pages = max(1, (count + 9) // 10)  # ~10 items per page
    try:
        for page_num in range(1, max_pages + 1):
            if len(results) >= count:
                break

            url = (
                f"https://weixin.sogou.com/weixin?type=2"
                f"&query={urllib.parse.quote(keyword)}&page={page_num}"
            )
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            raw_items = page.evaluate(_EXTRACT_JS)
            if not raw_items:
                break

            page_results = _process_raw_items(page, raw_items)
            if not page_results:
                break

            results.extend(page_results)

            # Short delay between pages to avoid anti-bot
            import time as _time
            _time.sleep(1.5)

    except Exception as e:
        print(f"[WeChat] Sogou search error: {e}")
    finally:
        page.close()
        ctx.close()
        if browser:
            browser.close()
        pw.stop()

    # Client-side date sort
    if sort_type == "date":
        results.sort(key=lambda r: r.get("_ts", 0), reverse=True)

    for r in results:
        r.pop("_ts", None)

    return results[:count]


def _resolve_sogou_url(search_page, sogou_url: str) -> str:
    """Click a Sogou redirect link to resolve the real mp.weixin.qq.com article URL.

    Sogou blocks direct navigation to /link?url=... with an anti-spider page.
    Clicking the link on the search results page (with Referer) works.
    """
    try:
        link_el = search_page.query_selector(f'a[href="{sogou_url}"]')
        if not link_el:
            # Try partial match — Sogou may truncate href in DOM
            import urllib.parse
            parsed = urllib.parse.urlparse(sogou_url)
            path_prefix = parsed.path + "?" + parsed.query[:60]
            link_el = search_page.query_selector(f'a[href^="{path_prefix}"]')

        if not link_el:
            return sogou_url

        ctx = search_page.context
        with ctx.expect_page(timeout=15000) as new_page_info:
            link_el.click()
        new_page = new_page_info.value

        try:
            new_page.wait_for_load_state("domcontentloaded", timeout=15000)
            new_page.wait_for_timeout(2000)
            final_url = new_page.url
            if "mp.weixin.qq.com" in final_url:
                return final_url
        finally:
            new_page.close()
    except Exception:
        pass

    return sogou_url


# ═══════════════════════════════════════════════════════════════════════════════
# Fetch: public article page scraping (no credentials)
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_wechat_article(url: str, timeout: int = 30) -> dict:
    """Fetch a single WeChat article via requests + BeautifulSoup.

    No credentials needed — works for publicly accessible mp.weixin.qq.com articles.
    """
    import requests as _requests
    from bs4 import BeautifulSoup as _bs

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    try:
        resp = _requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return _error(f"HTTP {resp.status_code}", url)
        html = resp.text
    except Exception as e:
        return _error(str(e), url)

    soup = _bs(html, "lxml")

    # Title
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content", "")
    if not title:
        h2 = soup.find("h2", id="activity-name")
        if h2:
            title = h2.get_text(strip=True)

    # Author (公众号名称)
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

    # Content
    content = ""
    js_content = soup.find("div", id="js_content")
    if js_content:
        for hidden in js_content.select(".rich_media_area_extra, script, style"):
            hidden.decompose()
        content = js_content.get_text(separator="\n", strip=True)
    if not content:
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
        "社媒数据": {"作者": author, "国家": "CN", "点赞": 0, "评论": 0,
                      "粉丝": 0, "播放量": None, "作者主页": []},
        "评论列表": [],
    }


def _error(msg: str, url: str) -> dict:
    return {
        "原文内容": f"(微信公众号抓取失败: {msg})",
        "发布时间": "", "来源平台": "微信公众号", "发布者类型": "未知",
        "互动数据": "", "原文链接": url,
        "社媒数据": {"作者": "", "国家": "CN", "点赞": 0, "评论": 0,
                      "粉丝": 0, "播放量": None, "作者主页": []},
        "评论列表": [],
    }


if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "Temu"
    print(f"=== 搜狗微信搜索: {keyword} ===")
    results = search_wechat_articles(keyword, count=10)
    print(f"找到 {len(results)} 篇文章\n")
    for i, r in enumerate(results[:5]):
        print(f"[{i+1}] {r['title'][:80]}")
        print(f"    作者: {r['author']}  |  时间: {r['publish_time']}")
        print(f"    URL: {r['url'][:120]}")
        print(f"    摘要: {r['snippet'][:100]}")
        print()
