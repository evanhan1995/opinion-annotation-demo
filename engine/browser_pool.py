# -*- coding: utf-8 -*-
"""Shared Playwright browser pool — single source of truth for browser config + lifecycle.

Usage:
    # Shared browser (headless singleton, multiple contexts share one Chromium)
    from engine.browser_pool import get_shared_browser, new_context
    browser, pw = get_shared_browser()
    ctx = new_context()
    page = ctx.new_page()
    # ... use page ...
    page.close()
    ctx.close()  # context is disposable; browser stays alive for next caller

    # One-shot independent browser (headless=False, persistent profile, etc.)
    from engine.browser_pool import launch_context
    ctx, browser, pw = launch_context(headless=False, user_data_dir="...")
    try:
        page = ctx.new_page()
        # ...
    finally:
        if browser: browser.close()
        else: ctx.close()
        pw.stop()
"""
import io
import sys
import threading
from pathlib import Path

import engine._compat

ENGINE_DIR = Path(__file__).resolve().parent

# ── Shared constants (single definition point) ──────────────────────────

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--exclude-switches=enable-automation",
    "--disable-infobars",
]

STEALTH_JS = ENGINE_DIR / "stealth.min.js"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/139.0.0.0 Safari/537.36"
)

DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}


# ── Shared headless browser singleton ───────────────────────────────────

_browser_lock = threading.Lock()
_shared_browser = None
_shared_pw = None


def get_shared_browser():
    """Thread-safe singleton. Returns (browser, playwright) for sync headless Chromium.

    The browser instance stays alive for the process lifetime.
    Callers create disposable contexts via new_context().
    """
    global _shared_browser, _shared_pw

    with _browser_lock:
        if _shared_browser is not None:
            return _shared_browser, _shared_pw

        from playwright.sync_api import sync_playwright

        _shared_pw = sync_playwright().start()
        _shared_browser = _shared_pw.chromium.launch(headless=True, args=BROWSER_ARGS)
        return _shared_browser, _shared_pw


def new_context(user_agent=None, viewport=None, stealth=True, **kwargs):
    """Create an isolated context on the shared browser.

    Args:
        user_agent: Override default UA (None = use DEFAULT_UA)
        viewport: Override default viewport (None = use DEFAULT_VIEWPORT)
        stealth: Inject stealth.min.js into every page in this context
        **kwargs: Passed to browser.new_context()
    """
    browser, _ = get_shared_browser()
    ctx = browser.new_context(
        user_agent=user_agent or DEFAULT_UA,
        viewport=viewport or DEFAULT_VIEWPORT,
        **kwargs,
    )
    if stealth and STEALTH_JS.exists():
        ctx.add_init_script(path=str(STEALTH_JS))
    return ctx


def cleanup_shared():
    """Close shared browser and stop Playwright. Call at process exit."""
    global _shared_browser, _shared_pw
    with _browser_lock:
        if _shared_browser:
            try:
                _shared_browser.close()
            except Exception:
                pass
            _shared_browser = None
        if _shared_pw:
            try:
                _shared_pw.stop()
            except Exception:
                pass
            _shared_pw = None


# ── One-shot independent browser launcher ───────────────────────────────

def launch_context(headless=True, user_data_dir=None, user_agent=None,
                   viewport=None, stealth=True, args=None):
    """Create an independent browser + context. For cases that can't use the shared pool.

    Args:
        headless: True for headless, False for visible (QR login)
        user_data_dir: If set, uses launch_persistent_context (persistent profile)
        user_agent: Override UA (None = DEFAULT_UA)
        viewport: Override viewport (None = DEFAULT_VIEWPORT)
        stealth: Inject stealth.min.js
        args: Override browser args (None = BROWSER_ARGS)

    Returns (context, browser_or_none, playwright_instance).

    Cleanup pattern:
        if browser: browser.close()
        else: context.close()
        pw.stop()
    """
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser_args = args if args is not None else BROWSER_ARGS
    ua = user_agent or DEFAULT_UA
    vp = viewport or DEFAULT_VIEWPORT

    if user_data_dir:
        # Persistent context — browser is embedded, no separate browser object
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            viewport=vp,
            args=browser_args,
            user_agent=ua,
        )
        if stealth and STEALTH_JS.exists():
            ctx.add_init_script(path=str(STEALTH_JS))
        return ctx, None, pw
    else:
        browser = pw.chromium.launch(headless=headless, args=browser_args)
        ctx = browser.new_context(user_agent=ua, viewport=vp)
        if stealth and STEALTH_JS.exists():
            ctx.add_init_script(path=str(STEALTH_JS))
        return ctx, browser, pw
