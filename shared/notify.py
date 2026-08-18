# -*- coding: utf-8 -*-
"""Feishu/Lark notification module.

Sends rich-card notifications to Feishu webhook(s).
Configure webhook URLs in notification_config.json or pass directly.
"""

import json
import logging
import os
import urllib.request
from pathlib import Path

_log = logging.getLogger("yuqing")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_NOTIFY_CONFIG_PATH = _PROJECT_ROOT / "notification_config.json"

_PLACEHOLDER_TOKEN = "YOUR_WEBHOOK_TOKEN"


def _normalize_hooks(hooks) -> list[dict]:
    """Normalize mixed string/dict webhook entries and drop unusable ones."""
    normalized = []
    for item in hooks:
        if isinstance(item, str):
            item = {"name": "", "url": item, "enabled": True, "trigger_level": "P0"}
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url or not item.get("enabled", True):
            continue
        if _PLACEHOLDER_TOKEN in url:
            _log.warning("Feishu webhook URL still contains placeholder token, skipping: %s", url[:40])
            continue
        normalized.append(item)
    return normalized


def _load_webhooks() -> list[dict]:
    """Load webhook entries from notification_config.json, fallback to FEISHU_WEBHOOK_URL env."""
    if _NOTIFY_CONFIG_PATH.exists():
        try:
            cfg = json.loads(_NOTIFY_CONFIG_PATH.read_text(encoding="utf-8"))
            hooks = _normalize_hooks(cfg.get("webhooks", []))
            if hooks:
                return hooks
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback to environment variable
    env_url = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
    if env_url and _PLACEHOLDER_TOKEN not in env_url:
        return [{"name": "env", "url": env_url, "enabled": True, "trigger_level": "P0"}]
    return []


def _build_card(title: str, body_text: str, fields: dict | None, level: str) -> dict:
    """Build a Feishu card v1 payload compatible with custom bot webhooks."""
    level_config = {
        "error": {"color": "red", "icon": "🚨"},
        "warning": {"color": "yellow", "icon": "⚠️"},
        "success": {"color": "green", "icon": "✅"},
        "info": {"color": "blue", "icon": "📢"},
    }
    lc = level_config.get(level, level_config["info"])

    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": body_text}},
    ]
    if fields:
        elements.append({
            "tag": "div",
            "fields": [
                {
                    "is_short": True,
                    "text": {"tag": "lark_md", "content": f"**{key}**\n{value}"},
                }
                for key, value in fields.items()
            ],
        })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{lc['icon']} {title}"},
                "template": lc["color"],
            },
            "elements": elements,
        },
    }


def _post_card(hooks: list[dict], title: str, body_text: str, fields: dict | None,
               level: str) -> int:
    """POST a card to the given webhook entries and return accepted count."""
    card = _build_card(title, body_text, fields, level)
    body = json.dumps(card, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}

    sent = 0
    for hook in hooks:
        url = hook["url"] if isinstance(hook, dict) else hook
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_body = resp.read().decode("utf-8", "replace")
            result = json.loads(resp_body)
            if result.get("code", 0) != 0:
                _log.warning(
                    "Feishu webhook rejected (%s): code=%s msg=%s",
                    url[:40], result.get("code"), result.get("msg"),
                )
                continue
            sent += 1
        except Exception as e:
            _log.warning("Feishu webhook failed (%s): %s", url[:40], e)
    return sent


def send_feishu_card(title: str, body_text: str, fields: dict | None = None,
                     level: str = "info", webhook_url: str | None = None,
                     webhook_urls: list[str] | None = None) -> int:
    """Send a Feishu interaction card via webhook.

    Args:
        title: Card title.
        body_text: Markdown body content.
        fields: Key-value pairs displayed as a horizontal field row.
        level: Color/icon theme — "error" (red), "warning" (yellow), "success" (green), "info" (blue).
        webhook_url: Override URL. If None, reads from notification_config.json.
        webhook_urls: Multiple override URLs (takes precedence over webhook_url).

    Returns:
        Number of webhooks that accepted the message.
    """
    if webhook_urls:
        hooks = _normalize_hooks([
            {"name": "", "url": url, "enabled": True, "trigger_level": "P0"}
            for url in webhook_urls
        ])
    elif webhook_url:
        hooks = _normalize_hooks([{"name": "", "url": webhook_url, "enabled": True, "trigger_level": "P0"}])
    else:
        hooks = _load_webhooks()
    if not hooks:
        return 0
    return _post_card(hooks, title, body_text, fields, level)


def send_severity_card(title: str, body_text: str, severity: str,
                       fields: dict | None = None) -> int:
    """Send a card to webhooks whose trigger_level includes the given severity."""
    matched = []
    for hook in _load_webhooks():
        trigger_level = str(hook.get("trigger_level", "P0"))
        if severity in set(trigger_level.replace("+", " ").split()):
            matched.append(hook)
    if not matched:
        return 0
    level = "error" if severity == "P0" else "warning"
    return _post_card(matched, title, body_text, fields, level)


def _metric_text(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def send_new_pending_case_card(url: str = "", comments: int = 0, likes: int = 0,
                               collects: int = 0, shares: int = 0) -> int:
    """Notify Feishu when a new pending case enters the knowledge base."""
    body = (
        "**有新的待处理case**\n\n"
        f"链接：{url or '暂无'}\n"
        f"评论：{_metric_text(comments)}\n"
        f"点赞：{_metric_text(likes)}\n"
        f"收藏：{_metric_text(collects)}\n"
        f"转发：{_metric_text(shares)}"
    )
    return send_feishu_card(title="📥 有新的待处理case", body_text=body, level="info")


def send_urgent_disposal_card(title: str = "", severity: str = "", platform: str = "",
                              url: str = "") -> int:
    """Notify Feishu (red/error) when a case is marked 立即处理 (urgent disposal).

    Distinct from send_new_pending_case_card: this fires on the 分流建议=立即处理
    action regardless of whether the URL is already ingested, so a human
    escalation always produces a visible alert.
    """
    body = (
        "**舆情需立即处置**\n\n"
        f"标题：{title or '暂无'}\n"
        f"严重度：{severity or '未知'}\n"
        f"平台：{platform or '未知'}\n"
        f"链接：{url or '暂无'}"
    )
    return send_feishu_card(title="舆情需立即处置", body_text=body, level="error")
