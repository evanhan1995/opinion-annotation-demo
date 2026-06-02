# -*- coding: utf-8 -*-
"""Sentinel Agent -- sentry: rule engine + SnowNLP pre-filter + topic discovery.

Responsibility (PRD v6.0):
  1. Rule engine: spam/gray market/irrelevant content filter
  2. SnowNLP pre-annotation: extreme-score sentiment pre-judgment (P2)
  3. Topic discovery: hot search -> keywords -> Monitor trigger (P4)

Isolation constraints:
  - MUST NOT modify KB (Curator's job)
  - MUST NOT generate action plans (Handler's job)
  - Read-only: inspects content, returns verdict
  - All LLM-routed cases go through Analyst via Orchestrator
"""

import re
from pathlib import Path

import engine._compat
from agents.shared import SentinelResult

# ═══════════════════════════════════════════════════════════════════════════════
# Rule patterns
# ═══════════════════════════════════════════════════════════════════════════════

# Spam / advertising -- high confidence reject
SPAM_KEYWORDS = [
    "加微信", "加我微信", "扫码加", "免费领取", "点击领取",
    "兼职招聘", "日赚", "月入过万", "在家可做",
    "关注公众号", "转发朋友圈", "集赞",
    "成人", "约炮", "裸聊", "视频裸",
    "赌博", "彩票预测", "必中",
    "代开", "代辦", "代办", "办证",
]

# Gray market / fraud services
GRAY_MARKET_KEYWORDS = [
    "代过", "可解", "秒过", "解封", "解限",
    "对公验证", "kyc", "银行验证",
    "刷单", "刷量", "刷粉", "刷赞", "买粉",
    "水军", "舆情删", "负面删", "删帖",
    "售卖", "出售数据", "数据包",
    "渠道", "强开", "内部渠道",
    "接单", "接码", "接码平台",
]

# Irrelevant personal / life content
IRRELEVANT_PATTERNS = [
    re.compile(r"今天天气"),
    re.compile(r"^(早|晚|下午|中午|晚上)安"),
    re.compile(r"^(打卡|签到|冒泡)"),
    re.compile(r"^转发微博$"),
    re.compile(r"^转发$"),
    re.compile(r"^[。，！？\s]*$"),  # empty/punctuation only
    re.compile(r"^分享图片$"),
]

# Obvious negative sentiment patterns
NEGATIVE_PATTERNS = [
    re.compile(r".*(垃圾|烂|坑|骗子|骗人|假的|差劲|恶心).*"),
    re.compile(r".*(退款|投诉|举报|曝光|维权).*"),
    re.compile(r".*(太差|很差|极差|非常差).*"),
    re.compile(r".*(千万别|千万不要|别买|避开|慎入).*"),
]

# Obvious positive sentiment patterns
POSITIVE_PATTERNS = [
    re.compile(r".*(好用|很棒|超赞|推荐|满意|赞了).*"),
    re.compile(r".*(好评|五星|完美|优秀|给力).*"),
    re.compile(r".*(性价比高|物超所值|值得).*"),
]

# Severity escalation keywords
SEVERITY_KEYWORDS = [
    (re.compile(r".*(死亡|致死|爆炸|火灾|地震|洪水).*"), "P0"),
    (re.compile(r".*(集体投诉|大规模|群体|游行|罢工).*"), "P1"),
    (re.compile(r".*(工商|药监|网信办|警方|立案).*"), "P1"),
]


def _check_patterns(text: str, patterns: list[re.Pattern]) -> bool:
    """Check if text matches any compiled regex pattern."""
    for p in patterns:
        if p.search(text):
            return True
    return False


def _check_keywords(text: str, keywords: list[str]) -> list[str]:
    """Return list of matched keywords."""
    hits = []
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            hits.append(kw)
    return hits


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def apply_rules(text: str, platform: str = "") -> SentinelResult:
    """Apply rule engine to content text.

    Returns SentinelResult with verdict:
      "reject"  — spam/gray market/irrelevant, skip entire pipeline
      "fast_track" — strong sentiment signal, skip LLM
      "pass"    — normal content, needs full Analyst (LLM) annotation
    """
    rule_hits = []
    spam_score = 0.0

    # 1. Check irrelevant patterns (personal life, empty, etc.)
    if _check_patterns(text, IRRELEVANT_PATTERNS):
        return SentinelResult(
            verdict="reject",
            reason="Irrelevant personal content (打卡/天气/空白)",
            spam_score=0.3,
            rule_hits=["irrelevant_pattern"],
        )

    # 2. Check spam keywords
    spam_hits = _check_keywords(text, SPAM_KEYWORDS)
    if spam_hits:
        return SentinelResult(
            verdict="reject",
            reason=f"Spam/advertising detected: {', '.join(spam_hits[:3])}",
            spam_score=0.9,
            rule_hits=spam_hits,
        )

    # 3. Check gray market keywords
    gray_hits = _check_keywords(text, GRAY_MARKET_KEYWORDS)
    if gray_hits:
        return SentinelResult(
            verdict="reject",
            reason=f"Gray market service detected: {', '.join(gray_hits[:3])}",
            spam_score=0.8,
            rule_hits=gray_hits,
        )

    # 4. Check severity escalation (fast_track for P0/P1 patterns)
    for pattern, severity in SEVERITY_KEYWORDS:
        if pattern.search(text):
            rule_hits.append(f"severity:{severity}")
            return SentinelResult(
                verdict="fast_track",
                reason=f"Severity escalation keyword matched: {severity}",
                spam_score=0.0,
                suggested_sentiment="负面",
                suggested_severity=severity,
                rule_hits=rule_hits,
            )

    # 5. Check obvious negative sentiment
    if _check_patterns(text, NEGATIVE_PATTERNS):
        return SentinelResult(
            verdict="fast_track",
            reason="Obvious negative sentiment pattern detected",
            spam_score=0.0,
            suggested_sentiment="负面",
            suggested_severity="P3",
            rule_hits=["negative_pattern"],
        )

    # 6. Check obvious positive sentiment
    if _check_patterns(text, POSITIVE_PATTERNS):
        return SentinelResult(
            verdict="fast_track",
            reason="Obvious positive sentiment pattern detected",
            spam_score=0.0,
            suggested_sentiment="正面",
            suggested_severity="P3",
            rule_hits=["positive_pattern"],
        )

    # 7. Default: pass to Analyst (LLM)
    return SentinelResult(
        verdict="pass",
        reason="No rule matched, needs LLM annotation",
        spam_score=0.0,
        rule_hits=rule_hits,
    )


def should_skip_pipeline(result: SentinelResult) -> bool:
    """Return True if the pipeline should skip this item entirely."""
    return result.verdict == "reject"


def should_skip_llm(result: SentinelResult) -> bool:
    """Return True if the item can skip LLM annotation (fast_track)."""
    return result.verdict == "fast_track"


# ═══════════════════════════════════════════════════════════════════════════════
# SnowNLP pre-filter (P2)
# ═══════════════════════════════════════════════════════════════════════════════

_SNOWNLP_AVAILABLE = False
try:
    from snownlp import SnowNLP as _SnowNLP
    _SNOWNLP_AVAILABLE = True
except ImportError:
    pass

# Only auto-pass at extreme scores to minimize false positives
SNOWNLP_NEGATIVE_THRESHOLD = 0.1   # < 0.1 → negative
SNOWNLP_POSITIVE_THRESHOLD = 0.99  # > 0.99 → positive


def apply_snownlp(text: str, rule_result: SentinelResult) -> SentinelResult:
    """Apply SnowNLP sentiment scoring as a second-layer pre-filter.

    Only called when rule engine verdict is "pass" (no rule matched).
    SnowNLP extreme scores can upgrade to "fast_track", but never "reject".

    Returns new SentinelResult (may be the same rule_result if no upgrade).
    """
    if not _SNOWNLP_AVAILABLE:
        return rule_result

    try:
        s = _SnowNLP(text[:500])
        score = s.sentiments
    except Exception:
        return rule_result

    # Only act on extreme scores (very high confidence)
    if score < SNOWNLP_NEGATIVE_THRESHOLD:
        return SentinelResult(
            verdict="fast_track",
            reason=f"SnowNLP extreme negative (score={score:.4f})",
            spam_score=0.0,
            suggested_sentiment="负面",
            suggested_severity="P3",
            rule_hits=rule_result.rule_hits + [f"snownlp:neg:{score:.4f}"],
        )
    elif score > SNOWNLP_POSITIVE_THRESHOLD:
        return SentinelResult(
            verdict="fast_track",
            reason=f"SnowNLP extreme positive (score={score:.4f})",
            spam_score=0.0,
            suggested_sentiment="正面",
            suggested_severity="P3",
            rule_hits=rule_result.rule_hits + [f"snownlp:pos:{score:.4f}"],
        )

    # Mid-range: stick with rule engine verdict, add snownlp info
    rule_result.rule_hits.append(f"snownlp:mid:{score:.4f}")
    return rule_result


# ═══════════════════════════════════════════════════════════════════════════════
# SVM sentiment classifier (v7.1 — replaces SnowNLP when model available)
# ═══════════════════════════════════════════════════════════════════════════════

_SVM_MODEL = None
_SVM_VECTORIZER = None
_SVM_LABELS = None
SVM_PROBA_THRESHOLD = 0.85


def _load_sentiment_model() -> bool:
    """Load SVM sentiment model from disk. Returns True if loaded."""
    global _SVM_MODEL, _SVM_VECTORIZER, _SVM_LABELS

    if _SVM_MODEL is not None:
        return True

    try:
        import joblib as _joblib
    except ImportError:
        return False

    model_path = Path(__file__).resolve().parent.parent / "engine" / "sentiment_model.pkl"
    if not model_path.exists():
        return False

    try:
        bundle = _joblib.load(str(model_path))
        _SVM_MODEL = bundle["svm"]
        _SVM_VECTORIZER = bundle["vectorizer"]
        _SVM_LABELS = bundle["labels"]
        return True
    except Exception:
        return False


def _extract_keyword_context(text: str, window_size: int = 100) -> str:
    """Extract text windows around monitored keywords for focused prediction.

    When keywords are found, concatenates context around each mention.
    Falls back to first 1000 chars of full text when no keywords match.
    """
    try:
        import json as _json
        kw_path = Path(__file__).resolve().parent.parent / "monitor_keywords.json"
        if kw_path.exists():
            kw_data = _json.loads(kw_path.read_text(encoding="utf-8"))
            keywords = [
                item["keyword"].lower()
                for item in kw_data.get("keywords", [])
                if item.get("active", True)
            ]
        else:
            keywords = []
    except Exception:
        keywords = []

    if not keywords:
        return text[:1000]

    text_lower = text.lower()
    windows = []
    for kw in keywords:
        idx = 0
        while True:
            pos = text_lower.find(kw.lower(), idx)
            if pos == -1:
                break
            start = max(0, pos - window_size)
            end = min(len(text), pos + len(kw) + window_size)
            window = text[start:end].strip()
            if window:
                windows.append(window)
            idx = pos + len(kw)

    if windows:
        return "。".join(windows)
    return text[:1000]


def _ml_sentiment_predict(text: str) -> SentinelResult | None:
    """Predict sentiment using SVM model.

    Returns SentinelResult(verdict="fast_track", ...) when confidence > threshold,
    or None when model unavailable or confidence too low.
    """
    global _SVM_MODEL, _SVM_VECTORIZER, _SVM_LABELS

    if _SVM_MODEL is None:
        if not _load_sentiment_model():
            return None

    try:
        import jieba as _jieba
        focused = _extract_keyword_context(text)
        tokenized = " ".join(_jieba.cut(focused[:1000]))
        features = _SVM_VECTORIZER.transform([tokenized])
        probas = _SVM_MODEL.predict_proba(features)[0]
    except Exception:
        return None

    max_idx = probas.argmax()
    max_proba = probas[max_idx]
    predicted_label = _SVM_LABELS[max_idx]

    if max_proba <= SVM_PROBA_THRESHOLD:
        return None

    # Map sentiment to severity
    severity_map = {"负面": "P3", "中性": "P3", "正面": "P3"}
    # Upgrade severity for strong negative keywords (duplicated from rules)
    negative_strong = ["死亡", "致死", "爆炸", "火灾", "集体投诉", "群体"]
    suggested_severity = "P3"
    for kw in negative_strong:
        if kw in text:
            if kw in ("死亡", "致死", "爆炸", "火灾"):
                suggested_severity = "P0"
            elif kw in ("集体投诉", "群体"):
                suggested_severity = "P1"
            break

    return SentinelResult(
        verdict="fast_track",
        reason=f"SVM {predicted_label} (proba={max_proba:.4f})",
        spam_score=0.0,
        suggested_sentiment=predicted_label,
        suggested_severity=suggested_severity,
        rule_hits=[f"svm:{predicted_label}:{max_proba:.4f}"],
    )


def screen_content(text: str, platform: str = "") -> SentinelResult:
    """Full sentinel pipeline: rules → SVM (v7.1) → SnowNLP fallback → verdict.

    This is the main entry point for Orchestrator.
    """
    result = apply_rules(text, platform)
    if result.verdict == "pass":
        # Try SVM first (v7.1)
        svm_result = _ml_sentiment_predict(text)
        if svm_result is not None:
            return svm_result
        # Fallback to SnowNLP
        result = apply_snownlp(text, result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Topic discovery (P4)
# ═══════════════════════════════════════════════════════════════════════════════

import json as _json
import time as _time
from urllib.request import Request as _Request, urlopen as _urlopen

# Cache hot topics for 30 minutes to avoid rate limiting
_TOPIC_CACHE: dict = {"data": [], "updated": 0}
_TOPIC_CACHE_TTL = 1800  # 30 min


def discover_topics(max_keywords: int = 20) -> list[str]:
    """Discover trending topics from public APIs.

    Tries multiple sources in order:
      1. Weibo hot search (public API)
      2. Baidu hot search
      3. Cached results (fallback)

    Returns list of keyword strings suitable for Monitor search.
    """
    # Return cache if fresh
    now = _time.time()
    if _TOPIC_CACHE["data"] and (now - _TOPIC_CACHE["updated"]) < _TOPIC_CACHE_TTL:
        return _TOPIC_CACHE["data"][:max_keywords]

    keywords = []

    # Try Weibo hot search
    weibo_keywords = _fetch_weibo_hot()
    if weibo_keywords:
        keywords.extend(weibo_keywords)

    # Try Baidu hot search if Weibo didn't give enough
    if len(keywords) < 10:
        baidu_keywords = _fetch_baidu_hot()
        if baidu_keywords:
            keywords.extend(baidu_keywords)

    # Deduplicate and limit
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen and len(kw) >= 2:
            seen.add(kw)
            unique.append(kw)
    unique = unique[:max_keywords]

    # Update cache
    _TOPIC_CACHE["data"] = unique
    _TOPIC_CACHE["updated"] = now

    return unique


def _fetch_weibo_hot() -> list[str]:
    """Fetch Weibo hot search keywords."""
    try:
        url = "https://weibo.com/ajax/side/hotSearch"
        req = _Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        with _urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        items = data.get("data", {}).get("realtime", [])
        keywords = []
        for item in items[:30]:
            word = item.get("word", "") or item.get("note", "")
            if word and len(word) >= 2:
                keywords.append(word.strip())
        return keywords
    except Exception:
        return []


def _fetch_baidu_hot() -> list[str]:
    """Fetch Baidu hot search keywords."""
    try:
        url = "https://top.baidu.com/board?tab=realtime"
        req = _Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with _urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Extract keywords from HTML (simple regex approach)
        import re
        # Match title patterns in Baidu hot search page
        keywords = []
        matches = re.findall(r'class="c-single-text-ellipsis">([^<]+)</div>', html)
        for m in matches[:30]:
            m = m.strip()
            if m and len(m) >= 2:
                keywords.append(m)
        return keywords
    except Exception:
        return []


def clear_topic_cache():
    """Clear topic cache (for testing)."""
    global _TOPIC_CACHE
    _TOPIC_CACHE = {"data": [], "updated": 0}


def _get_cache_age() -> float:
    """Return cache age in seconds (for testing)."""
    return _time.time() - _TOPIC_CACHE["updated"] if _TOPIC_CACHE["updated"] else 0
