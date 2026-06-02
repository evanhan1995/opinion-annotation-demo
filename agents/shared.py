# -*- coding: utf-8 -*-
"""
舆情指挥系统 — Shared Infrastructure
LLM model factory, JSON parsing, UTF-8 adapter, and common utilities.

Model assignment (PRD §4.2):
  Analyst   → DeepSeek (reasoning-heavy, strict JSON)
  Handler   → DeepSeek (logical consistency)
  Curator   → DeepSeek (Q&A search)
  Daily Rpt → MiniMax (Chinese text generation, cost-effective)
  Monitor   → No LLM (pure code)
  Scraper   → No LLM (pure code)
"""
import io
import json
import os
import re
import sys
from concurrent import futures
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── UTF-8 adapter (Windows) ───────────────────────────────────────────
if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Project paths ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = PROJECT_ROOT / "engine"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
WIKI_DIR = PROJECT_ROOT / "wiki"
RAW_DIR = PROJECT_ROOT / "raw"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# ── Config loading ─────────────────────────────────────────────────────
def _load_config() -> dict:
    config_path = ENGINE_DIR / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

_CONFIG = _load_config()


# ── Timeout wrapper (shared by all agents) ──────────────────────────────
def call_with_timeout(fn, timeout: float, *args, **kwargs):
    """Run fn(*args, **kwargs) in a thread with hard wall-clock timeout.

    Returns (result, None) on success, (None, error_string) on timeout/exception.
    Use this for ALL external calls (API, scraper, asyncio) that run inside
    daemon threads where SDK-level timeouts are not reliable.
    """
    executor = futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = executor.submit(fn, *args, **kwargs)
        try:
            return fut.result(timeout=timeout), None
        except futures.TimeoutError:
            return None, f"操作超时 ({timeout}s)"
        except Exception as e:
            return None, str(e)
    finally:
        executor.shutdown(wait=False)


# ── Model Registry (PRD §4.3) ─────────────────────────────────────────
@dataclass
class ModelConfig:
    provider: str
    model: str
    api_key: str
    base_url: str

def _build_registry() -> dict:
    registry = {}
    # DeepSeek
    ds_key = os.environ.get("DEEPSEEK_API_KEY", _CONFIG.get("api_key", ""))
    ds_base = os.environ.get("DEEPSEEK_BASE_URL", _CONFIG.get("api_base", "https://api.deepseek.com"))
    ds_model = _CONFIG.get("model", "deepseek-chat")
    registry["deepseek"] = ModelConfig("deepseek", ds_model, ds_key, ds_base)

    # MiniMax (if configured)
    mm_key = os.environ.get("MINIMAX_API_KEY", _CONFIG.get("minimax_api_key", ""))
    mm_base = os.environ.get("MINIMAX_BASE_URL", _CONFIG.get("minimax_api_base", "https://api.minimax.chat/v1"))
    mm_model = _CONFIG.get("minimax_model", "abab6.5s-chat")
    registry["minimax"] = ModelConfig("minimax", mm_model, mm_key, mm_base)

    return registry

MODEL_REGISTRY = _build_registry()


def get_llm(provider: str = "deepseek"):
    """Return (openai.Client, model_name) for the given provider.

    Usage:
        client, model = get_llm("deepseek")
        response = client.chat.completions.create(model=model, ...)
    """
    cfg = MODEL_REGISTRY.get(provider)
    if cfg is None:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(MODEL_REGISTRY.keys())}")
    if not cfg.api_key:
        raise ValueError(f"API key not configured for provider: {provider}")
    from openai import OpenAI
    client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    return client, cfg.model


# ── JSON parsing (shared by all agents) ────────────────────────────────
def extract_json(text: str) -> list | dict:
    """Extract JSON from LLM output, handling markdown code fences."""
    content = text.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)


def safe_json_parse(text: str, default=None):
    """Parse JSON safely, returning default on failure."""
    try:
        return extract_json(text)
    except (json.JSONDecodeError, IndexError, ValueError):
        return default


# ── Prompt loading ─────────────────────────────────────────────────────
def load_prompt(name: str) -> str:
    """Load a System Prompt from prompts/{name}.txt"""
    path = PROMPTS_DIR / f"{name}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


# ── Common dataclasses ─────────────────────────────────────────────────
@dataclass
class RawData:
    """Standardized scraped content (PRD §5.2 S-04)."""
    url: str
    platform: str           # xhs | douyin | youtube
    title: str
    content: str
    author: str = ""
    author_id: str = ""
    publish_time: str = ""
    likes: int = 0
    comments_raw: list[str] = field(default_factory=list)
    view_count: int = 0
    source_keyword: str = ""  # which Monitor keyword triggered this (empty if manual)


@dataclass
class Annotation:
    """Analyst output (PRD §5.3)."""
    url: str
    platform: str
    severity: str           # P0 | P1 | P2 | P3
    severity_reason: str
    sentiment: str          # 正面 | 中性 | 负面
    risk_tags: list[str]
    triage: str             # 内部研判 | 上升法务 | 上升PR | 忽略
    comment_risk: str       # 红 | 黄 | 绿
    category: str = ""
    relevance: str = "relevant"  # relevant | irrelevant_{keyword}_{platform}
    relevance_reason: str = ""
    summary: str = ""


@dataclass
class ActionPlan:
    """Handler output (PRD §5.4)."""
    case_id: str
    status: str             # 待跟进 | 处理中 | 已处理 | 已放弃 | 忽略
    steps: list[str]
    escalated_departments: list[str]
    deadline: str
    notes: str = ""


@dataclass
class KBEntry:
    """Curator case entry metadata (PRD §5.5)."""
    case_id: str
    url: str
    platform: str
    severity: str
    status: str
    ingested_at: str
    title: str
    file_path: str = ""


@dataclass
class SentinelResult:
    """Sentinel Agent pre-filter verdict (PRD v6.0).

    verdict:
      "pass"        — normal content, proceed to Analyst (LLM)
      "reject"      — spam/ad/gray market, skip entire pipeline
      "fast_track"  — obvious sentiment, skip LLM, use suggested_* fields
    """
    verdict: str            # "pass" | "reject" | "fast_track"
    reason: str             # human-readable explanation
    spam_score: float = 0.0       # 0.0-1.0 estimated spam probability
    suggested_sentiment: str = ""  # for fast_track: 正面/中性/负面
    suggested_severity: str = ""   # for fast_track: P0/P1/P2/P3
    rule_hits: list[str] = field(default_factory=list)


@dataclass
class ForumResult:
    """Forum Agent cross-validation result (PRD v6.0)."""
    case_id: str
    related_cases: list[str] = field(default_factory=list)  # linked case IDs
    contradictions: list[str] = field(default_factory=list)  # discrepancy descriptions
    host_verdict: str = ""  # Forum Host LLM summary
    needs_review: bool = False  # flag for manual review


# ═══════════════════════════════════════════════════════════════════════════════
# Shared conversion functions (single source of truth for all agents)
# ═══════════════════════════════════════════════════════════════════════════════

# Platform name mapping: agent key ↔ engine Chinese label
PLATFORM_KEY_TO_LABEL = {
    "youtube": "YouTube", "xiaohongshu": "小红书", "douyin": "抖音",
    "bilibili": "B站", "weibo": "微博", "wechat": "微信公众号",
}
PLATFORM_LABEL_TO_KEY = {v: k for k, v in PLATFORM_KEY_TO_LABEL.items()}


def rawdata_to_engine_dict(raw: RawData) -> dict:
    """Convert RawData to engine/scraper dict format.

    Single source of truth — used by Analyst, Curator, and Ingestor.
    """
    comments = []
    for c in raw.comments_raw:
        if isinstance(c, str):
            comments.append({"内容": c})
        elif isinstance(c, dict):
            comments.append(c)

    return {
        "原文内容": f"标题：{raw.title}\n\n{raw.content}" if raw.title else raw.content,
        "来源平台": PLATFORM_KEY_TO_LABEL.get(raw.platform, raw.platform),
        "发布者类型": raw.author,
        "互动数据": f"点赞{raw.likes}, 播放{raw.view_count}",
        "发布时间": raw.publish_time,
        "原文链接": raw.url,
        "评论列表": comments,
        "社媒数据": {
            "作者": raw.author,
            "国家": "",
            "点赞": raw.likes,
            "评论": len(raw.comments_raw),
            "粉丝": 0,
            "播放量": raw.view_count,
            "作者主页": [],
        },
    }


def engine_dict_to_rawdata(engine_dict: dict, url: str) -> RawData:
    """Convert engine/scraper.py dict format to RawData dataclass.

    Single source of truth — used by Scraper Agent.
    """
    social = engine_dict.get("社媒数据", {}) or {}
    content_text = engine_dict.get("原文内容", "")
    raw_platform = engine_dict.get("来源平台", "")
    agent_platform = PLATFORM_LABEL_TO_KEY.get(raw_platform, raw_platform.lower())

    # Split content into title + body
    title = ""
    body = content_text
    if content_text.startswith("标题："):
        lines = content_text.split("\n")
        title = lines[0].replace("标题：", "").strip()
        body = "\n".join(lines[1:]).strip()

    comments = engine_dict.get("评论列表", [])
    comments_raw = []
    for c in comments:
        if isinstance(c, dict):
            text = c.get("内容", "") or c.get("text", "")
            if text:
                comments_raw.append(text.strip()[:500])
        elif isinstance(c, str):
            if c.strip():
                comments_raw.append(c.strip()[:500])

    return RawData(
        url=url,
        platform=agent_platform,
        title=title,
        content=body,
        author=social.get("作者", "") or "",
        publish_time=engine_dict.get("发布时间", "") or "",
        likes=social.get("点赞", 0) or 0,
        comments_raw=comments_raw,
        view_count=social.get("播放量", 0) or 0,
    )


def annotation_to_engine_dict(ann: Annotation) -> dict:
    """Convert Annotation to engine/annotate result dict format.

    Single source of truth — used by Curator and Ingestor.
    """
    return {
        "严重度评级": ann.severity,
        "严重度理由": ann.severity_reason,
        "情感分析": {"整体情感": ann.sentiment},
        "风险标签": ann.risk_tags,
        "分流建议": ann.triage,
        "评论区分析": {"评论红绿灯": {"红": 1 if ann.comment_risk == "红" else 0,
                                   "黄": 1 if ann.comment_risk == "黄" else 0,
                                   "绿": 1 if ann.comment_risk == "绿" else 0}},
        "舆情分类": ann.category.split("|") if ann.category else [],
        "摘要": ann.summary,
    }
