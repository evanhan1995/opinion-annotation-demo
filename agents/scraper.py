# -*- coding: utf-8 -*-
"""
舆情指挥系统 — Scraper Agent (采集员)

Responsibility (PRD §5.2):
  Fetch URL → standardized RawData for 3 platforms: XHS, Douyin, YouTube.

Isolation constraints:
  - MUST NOT do any annotation/rating (Analyst's job)
  - MUST NOT decide whether to ingest into KB (Curator's job)
  - Returns ONLY structured raw data

Model: No LLM needed — pure scraping/crawling logic.
"""
import io
import sys
from pathlib import Path
from typing import Optional

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agents.shared import RawData, engine_dict_to_rawdata


# ── Platform detection ──────────────────────────────────────────────────
def detect_platform(url: str) -> str:
    """Detect platform from URL."""
    url_lower = url.lower()
    if "xiaohongshu.com" in url_lower or "xhslink.com" in url_lower:
        return "xiaohongshu"
    if "douyin.com" in url_lower or "tiktok.com" in url_lower:
        return "douyin"
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    return "unknown"


# ── Per-platform fetchers ───────────────────────────────────────────────
def _fetch_xhs(url: str) -> RawData:
    from engine.xhs_fetcher import fetch_xhs_note
    result = fetch_xhs_note(url)
    return engine_dict_to_rawdata(result, url)


def _fetch_douyin(url: str) -> RawData:
    from engine.tt_fetcher import fetch_douyin_video
    result = fetch_douyin_video(url)
    return engine_dict_to_rawdata(result, url)


def _fetch_youtube(url: str) -> RawData:
    from engine.scraper import scrape
    result = scrape(url)
    return engine_dict_to_rawdata(result, url)


# Only 3 platforms active (PRD §1.3). Reddit/X in engine/scraper.py are
# preserved but not wired — restore when Platform Expansion hits Phase 6-7.
_FETCHERS = {
    "xiaohongshu": _fetch_xhs,
    "douyin": _fetch_douyin,
    "youtube": _fetch_youtube,
}


# ── Main entry ─────────────────────────────────────────────────────────
def fetch(url: str, timeout: int = 120) -> RawData:
    """Fetch content from URL. Returns standardized RawData.

    Called by Orchestrator.run_passive_analysis() or during active_monitor loop.
    """
    platform = detect_platform(url)
    fetcher = _FETCHERS.get(platform)
    if fetcher is None:
        return RawData(url=url, platform="unknown", title="", content="",
                       comments_raw=[f"Unsupported platform: {platform}"])
    try:
        return fetcher(url)
    except Exception as e:
        return RawData(url=url, platform=platform, title="", content="",
                       comments_raw=[f"Fetch error: {str(e)}"])


# ── Manual feed fallback (PRD S-06) ────────────────────────────────────
def manual_feed(url: str, title: str, content: str, platform: str = "",
                comments: list[str] | None = None) -> RawData:
    """Human-provided content when Scraper fails (PRD S-06 anti-crawl fallback).

    Bypasses all scraping — directly assembles RawData from manual input.
    """
    pf = platform or detect_platform(url)
    return RawData(
        url=url, platform=pf, title=title, content=content,
        comments_raw=comments or [],
    )
