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


def _load_webhooks() -> list[str]:
    """Load webhook URLs from notification_config.json, fallback to FEISHU_WEBHOOK_URL env."""
    if _NOTIFY_CONFIG_PATH.exists():
        try:
            cfg = json.loads(_NOTIFY_CONFIG_PATH.read_text(encoding="utf-8"))
            hooks = cfg.get("webhooks", [])
            if hooks:
                return hooks
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback to environment variable
    env_url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if env_url:
        return [env_url]
    return []


def send_feishu_card(title: str, body_text: str, fields: dict | None = None,
                     level: str = "info", webhook_url: str | None = None):
    """Send a Feishu interaction card via webhook.

    Args:
        title: Card title (blue header).
        body_text: Markdown body content.
        fields: Key-value pairs displayed as a horizontal field row.
        level: Color/icon theme — "error" (red), "warning" (yellow), "success" (green), "info" (blue).
        webhook_url: Override URL. If None, reads from notification_config.json.
    """
    level_config = {
        "error": {"color": "red", "icon": "🚨"},
        "warning": {"color": "yellow", "icon": "⚠️"},
        "success": {"color": "green", "icon": "✅"},
        "info": {"color": "blue", "icon": "📢"},
    }
    lc = level_config.get(level, level_config["info"])

    field_list = []
    if fields:
        for key, value in fields.items():
            field_list.append({
                "is_short": True,
                "text": {"tag": "lark_md", "content": f"**{key}**\n{value}"}
            })

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{lc['icon']} {title}"},
                "template": lc["color"],
            },
            "elements": [
                {"tag": "markdown", "content": body_text},
            ],
        },
    }
    if field_list:
        card["card"]["elements"].append({"tag": "column_set", "flex_mode": "bisect", "background_style": "default", "columns": field_list})

    webhooks = [webhook_url] if webhook_url else _load_webhooks()
    if not webhooks:
        return

    body = json.dumps(card, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}

    for hook in webhooks:
        try:
            req = urllib.request.Request(hook, data=body, headers=headers, method="POST")
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            _log.warning("Feishu webhook failed (%s): %s", hook[:40], e)
