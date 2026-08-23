# -*- coding: utf-8 -*-
"""
WeChat (微信公众号) article search + in-session fetch.

Search: Playwright + stealth.js → weixin.sogou.com (public, no login needed)
Fetch:  in-session extraction via _resolve_sogou_url → cached for Scraper.
        (A direct requests-based fetch is not viable — WeChat returns a
        captcha wall to unauthenticated requests, and the permanent-link `sn`
        signature is never exposed to the page. See CLAUDE.md.)

Architecture:
  search_wechat_articles(keyword) → Sogou WeChat search → article URL list
  _resolve_sogou_url() → in-session article extraction → _ARTICLE_CACHE
  get_cached_article() → served by engine.scraper._scrape_wechat
"""

import io
import sys
import re
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

        real_url, extracted_time = _resolve_sogou_url(page, sogou_url)
        if extracted_time:
            publish_time = extracted_time

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


# In-session article cache.  mp.weixin.qq.com articles are only reliably
# fetchable during the Sogou→WeChat redirect session: the permanent-link `sn`
# signature is never surfaced to the page (only `__biz`/`mid`/`idx` are), and a
# permanent URL without `sn` returns "参数错误".  So Monitor extracts the full
# article in-session and caches it here; the downstream Scraper serves it from
# this cache instead of re-hitting WeChat's expired-token / anti-bot wall.
_ARTICLE_CACHE: Dict[str, dict] = {}


def get_cached_article(url: str) -> Optional[dict]:
    """Return the in-session article dict for a URL, or None if not cached."""
    return _ARTICLE_CACHE.get(url)


def _extract_wechat_page(page, url: str) -> dict:
    """Extract the standardized article dict from an already-loaded WeChat page.

    Must be called while the redirect session is still live (inside
    _resolve_sogou_url).  Mirrors the success return of scraper._scrape_wechat.
    """
    def _txt(selector):
        try:
            el = page.query_selector(selector)
            return el.inner_text().strip() if el else ""
        except Exception:
            return ""

    title = _txt("h2#activity-name") or _txt("h1#activity-name")
    author = _txt("#js_name")
    publish_time = _txt("em#publish_time") or _txt(".rich_media_meta_text")
    content = _txt("#js_content") or _txt(".rich_media_content")

    body = content[:3000] if content else ""
    if title:
        # 标题非空时用「标题：」前缀，让 engine_dict_to_rawdata 能解析出 RawData.title；
        # 标题为空时不加前缀，保证正文格式一致（避免哈希不稳定）。
        raw_content = f"标题：{title}\n\n{body}" if body else f"标题：{title}"
    else:
        raw_content = body

    return {
        "原文内容": raw_content,
        "发布时间": publish_time,
        "来源平台": "微信公众号",
        "发布者类型": f"公众号: {author}" if author else "未知",
        "互动数据": "",
        "原文链接": url,
        "社媒数据": {"作者": author, "国家": "CN", "点赞": 0, "评论": 0,
                      "粉丝": 0, "播放量": None, "作者主页": []},
        "评论列表": [],
    }


def _resolve_sogou_url(search_page, sogou_url: str) -> tuple[str, str]:
    """Navigate the Sogou redirect into the live WeChat article and extract it.

    Returns (article_url, publish_time).

    The canonical `__biz` permanent URL cannot be reconstructed here: WeChat
    withholds the `sn` signature from the page (only `__biz`/`mid`/`idx` are
    exposed), and a permanent URL without `sn` shows "参数错误".  So instead of
    returning a dead permanent URL, we extract the full article while the
    redirect session is still live and cache it for the downstream Scraper.
    article_url is the session URL the article was loaded at (works for
    in-session viewing and as the cache key), never a guessed __biz URL.
    """
    publish_time = ""
    article_url = sogou_url
    ctx = search_page.context
    page = None
    try:
        page = ctx.new_page()
        search_url = search_page.url
        page.goto(sogou_url, timeout=15000, wait_until="domcontentloaded",
                  referer=search_url)

        # The Sogou intermediate page JS-redirects to the real mp.weixin.qq.com
        # article. Actively wait for that redirect so page.url is the session
        # article URL and the article DOM is loaded.
        try:
            page.wait_for_url("**mp.weixin.qq.com**", timeout=12000)
        except Exception:
            pass

        if "mp.weixin.qq.com" in page.url:
            article_url = page.url
            # Extract + cache the full article while the session is live.
            article = _extract_wechat_page(page, article_url)
            _ARTICLE_CACHE[article_url] = article
            publish_time = article.get("发布时间", "")
            # In-session body may still show "参数错误" if the token expired
            # mid-flight; cache it anyway so the Scraper reports the real reason.
        else:
            # Redirect did not complete — nothing usable to cache.
            article_url = sogou_url
    except Exception:
        pass
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass

    return article_url, publish_time


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
