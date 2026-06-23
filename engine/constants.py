# -*- coding: utf-8 -*-
"""Shared constants for the opinion annotation system.

Single source of truth for platform mappings, category labels, etc.
"""

# ── Platform key (agent/engine internal) ↔ Chinese label ──────────────────
PLATFORM_KEY_TO_LABEL = {
    "youtube": "YouTube",
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "bilibili": "B站",
    "weibo": "微博",
    "wechat": "微信公众号",
    "x": "X",
    "reddit": "Reddit",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "web": "通用网页",
    "news": "新闻媒体",
    "forum": "论坛",
    "other": "其他",
}

PLATFORM_LABEL_TO_KEY = {v: k for k, v in PLATFORM_KEY_TO_LABEL.items()}

# ── Platform abbreviation (Chinese label → short key for filenames) ────────
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

# ── Category options (used by annotator and UI) ───────────────────────────
CATEGORY_OPTIONS = [
    "产品体验", "产品质量", "售后服务", "物流配送",
    "价格策略", "营销活动", "竞品攻击", "KOL/网红负面",
    "员工行为", "企业社会责任", "数据安全/隐私",
    "法律法规/合规", "大规模传播", "其他",
]
