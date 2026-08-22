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

# ── 可纠偏/可对比字段清单（compare_and_decide 与 diff_annotations 共享）──────
# 类型标记：
#   "scalar" — 标量（字符串/数字等），用相等性判定
#   "list"   — 列表（顺序不敏感，用集合对称差判定是否有变化）
#   "dict"   — 字典，用相等性判定
# 字段名含点号表示嵌套路径（如 "情感分析.整体情感"）。
ANNOTATION_COMPARABLE_FIELDS = [
    ("严重度评级", "scalar"),
    ("分流建议", "scalar"),
    ("情感分析.整体情感", "scalar"),
    ("叙事分类", "scalar"),
    ("真实性评估", "scalar"),
    ("风险标签", "list"),
    ("舆情分类", "list"),
    ("评论区分析.评论红绿灯", "dict"),
    ("评论区分析.评论总结", "scalar"),
    ("摘要", "scalar"),
    ("严重度理由", "scalar"),
]


def _get_nested_value(d: dict, path: str):
    """按点号路径取嵌套值（如 "情感分析.整体情感"），缺失返回 None。"""
    cur = d
    for key in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def extract_annotation_diffs(a: dict, b: dict) -> list[dict]:
    """对比两个标注，返回扁平差异列表（compare_and_decide / diff_annotations 共享）。

    返回 [{"field": ..., "old_value": ..., "new_value": ...}, ...]。
    字段范围由 ANNOTATION_COMPARABLE_FIELDS 定义；list 字段用集合对称差判定
    （顺序不敏感），scalar/dict 用相等性判定。
    """
    diffs = []
    for field, ftype in ANNOTATION_COMPARABLE_FIELDS:
        ov = _get_nested_value(a, field)
        nv = _get_nested_value(b, field)
        if ftype == "list":
            ov_set = set(ov) if isinstance(ov, list) else set()
            nv_set = set(nv) if isinstance(nv, list) else set()
            changed = ov_set != nv_set
        else:
            changed = ov != nv
        if changed:
            diffs.append({"field": field, "old_value": ov, "new_value": nv})
    return diffs
