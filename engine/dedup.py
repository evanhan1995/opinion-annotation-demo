"""统一去重模块 —— 微信/各平台稳定去重键 + 正文内容哈希。

Monitor（搜索链路）与 Ingest（入库链路）共用此模块，避免去重口径各自为政。
微信 URL 是搜狗临时 token（每次搜索轮换），因此：
- 搜索链路去重键用「归一化标题 | 作者」（stable_dedup_key / normalize_title）；
- 入库链路去重键用「正文内容哈希」（compute_content_hash / strip_dynamic_footer）。

两者针对同一「URL 不稳定」根因，但适用场景不同：搜索结果只有标题/作者，
入库时有完整正文，故用不同键。
"""

import hashlib
import re
import unicodedata

_ZERO_WIDTH_CHARS = ["​", "‌", "‍", "﻿", "‎", "‏", " "]
_TRAILING_DECOR = r"[\s#•●▲△▼▽■□★☆♦→←↑↓]+$"

# 正文末尾动态 footer 里的相对时间（「原文/地区/X分钟前」），随抓取时刻变化
_RELATIVE_TIME_TAIL = re.compile(
    r"(?:[,，]\s*)?(?:\d+\s*(?:分钟|小时|天|秒|周|个月|年)?前|昨天|前天|刚刚)(?:\s*[,，])?\s*$"
)


def normalize_title(t: str) -> str:
    """归一化微信标题：去零宽、全角→半角、折叠空白、剥尾随装饰符号。"""
    if not t:
        return ""
    for z in _ZERO_WIDTH_CHARS:
        t = t.replace(z, "")
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(_TRAILING_DECOR, "", t).strip()
    return t


def stable_dedup_key(platform: str, url: str, title: str = "", author: str = "") -> str:
    """各平台稳定去重键：微信用归一化 title+author（URL 是搜狗临时 token），其余平台用 URL。"""
    if platform == "wechat":
        return f"{normalize_title(title)}|{(author or '').strip()}"
    return url


def strip_dynamic_footer(text: str) -> str:
    """剥正文末尾的动态 footer（「原文/地区/X分钟前」里的相对时间），只锚定末尾，不碰中间时间类文字。"""
    if not text:
        return ""
    t = text.rstrip()
    m = _RELATIVE_TIME_TAIL.search(t)
    return t[: m.start()].rstrip() if m else t


def normalize_body_for_hash(text: str) -> str:
    """哈希输入规范化：剥「标题：」前缀 + 动态 footer，再小写折叠空白。

    标题不参与哈希——标题抓取可能波动，掺进去会让同一篇文章两次哈希不一致。
    """
    t = re.sub(r"^标题：[^\n]*\n\s*\n?", "", text, count=1)
    t = strip_dynamic_footer(t)
    t = t.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def compute_content_hash(body: str) -> str:
    """微信内容哈希：sha256(规范化正文)[:16]。只 hash 正文，不掺标题/摘要。"""
    return hashlib.sha256(normalize_body_for_hash(body).encode("utf-8")).hexdigest()[:16]
