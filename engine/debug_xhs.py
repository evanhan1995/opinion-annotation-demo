# -*- coding: utf-8 -*-
"""XHS Cookie debug script — one-shot diagnostic for Phase 17c.

Usage: python engine/debug_xhs.py [xhs_note_url]
"""

import json
import sys
import time
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from engine.xhs_fetcher import (
    XhsApiClient,
    _load_cached_cookies,
    bootstrap_cookies,
    get_cookie_string,
    parse_note_url,
)
from xhshow import Xhshow

# ═══════════════════════════════════════════════════════════════════
# Step 1: Cookie inventory
# ═══════════════════════════════════════════════════════════════════

print("=" * 60)
print("STEP 1: Cookie inventory")
print("=" * 60)

cookie_str = get_cookie_string(allow_bootstrap=False)
if not cookie_str:
    print("[WARN] No cached cookies. Need to bootstrap first.")
    sys.exit(1)

xh = Xhshow()
cookie_dict = xh._parse_cookies(cookie_str)

print(f"\nTotal cookies: {len(cookie_dict)}")
print(f"Key cookies present:")
for key in ["a1", "web_session", "webId", "acw_tc", "id_token", "gid", "websectiga",
            "xsecappid", "sec_poison_id", "abRequestId", "ets", "loadts",
            "x-rednote-datactry", "x-rednote-holderctry", "unread", "webBuild"]:
    val = cookie_dict.get(key, "")
    status = "PRESENT" if val else "MISSING"
    snippet = (val[:30] + "...") if val else ""
    print(f"  [{status}] {key}: {snippet}")

# ═══════════════════════════════════════════════════════════════════
# Step 2: API call diagnosis
# ═══════════════════════════════════════════════════════════════════

url = sys.argv[1] if len(sys.argv) > 1 else None
if not url:
    print("\n[SKIP] Step 2 — no URL provided. Usage: python engine/debug_xhs.py <url>")
    sys.exit(0)

print("\n" + "=" * 60)
print("STEP 2: API call diagnosis")
print("=" * 60)

parsed = parse_note_url(url)
print(f"\nURL parsed:")
print(f"  note_id: {parsed['note_id']}")
print(f"  xsec_token: {parsed['xsec_token'][:30]}...")
print(f"  xsec_source: {parsed['xsec_source']}")

# Test: get note detail
client = XhsApiClient(cookie_str)
try:
    print(f"\nCalling get_note_detail({parsed['note_id']})...")
    note = client.get_note_detail(parsed["note_id"], parsed["xsec_token"], parsed["xsec_source"])
    print(f"\n[OK] Note detail received:")
    print(json.dumps(note, ensure_ascii=False, indent=2)[:2000])

    # Test comments
    print(f"\n--- Testing comments ---")
    comments = client.get_note_comments(parsed["note_id"], parsed["xsec_token"], max_count=5)
    print(f"[OK] Comments received: {len(comments)}")
    if comments:
        print(json.dumps(comments[0], ensure_ascii=False, indent=2)[:500])

    print(f"\n[SUCCESS] XHS fetch works with current cookies!")

except Exception as e:
    err_msg = str(e)
    print(f"\n[FAIL] API call failed: {err_msg}")

    # Detailed error analysis
    if "XHS_COOKIE_EXPIRED" in err_msg:
        print("\n  → Cookie expired or invalid session")
        print("  → Action: re-bootstrap cookies via Playwright QR scan")
    elif "XHS API error" in err_msg:
        print(f"\n  → API returned error (not cookie-related)")
        # Try to extract more from the error
    elif "登录" in err_msg:
        print("\n  → Login required — cookie session is dead")
        print("  → Action: re-bootstrap cookies")

    # Try a raw request to see what the API actually returns
    print(f"\n--- Raw API probe ---")
    import httpx
    probe_headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.xiaohongshu.com/",
    }
    try:
        raw = httpx.get(
            f"https://edith.xiaohongshu.com/api/sns/web/v1/feed",
            params={
                "source_note_id": parsed["note_id"],
                "xsec_token": parsed["xsec_token"],
                "xsec_source": parsed["xsec_source"],
            },
            headers=probe_headers,
            timeout=15,
        )
        print(f"  HTTP status: {raw.status_code}")
        print(f"  Response (first 500 chars):\n{raw.text[:500]}")
    except Exception as e2:
        print(f"  Raw probe failed: {e2}")

finally:
    client.close()
