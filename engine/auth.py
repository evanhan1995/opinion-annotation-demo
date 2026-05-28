# -*- coding: utf-8 -*-
"""Authentication module for 舆情标注系统.

Role-based access control with SHA-256 password hashing.
Credentials stored in config/auth_config.json.
"""

import hashlib
import json
from pathlib import Path

AUTH_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "auth_config.json"

ROLE_TABS = {
    "admin": ["📊 总览", "📡 Monitor", "📝 录入研判", "📋 案例处置", "📚 知识库", "📊 报告", "⚠️ 高危追踪", "⚙️ 设置"],
    "monitor": ["📊 总览", "📝 录入研判", "📚 知识库", "⚙️ 设置"],
    "disposition": ["📊 总览", "📋 案例处置", "📚 知识库", "⚙️ 设置"],
    "report_editor": ["📊 总览", "📊 报告", "📚 知识库", "⚙️ 设置"],
}

ROLE_LABELS = {
    "admin": "管理员",
    "monitor": "监测组",
    "disposition": "处置组",
    "report_editor": "日报编辑",
}


def _load_auth_config() -> dict:
    if not AUTH_CONFIG_PATH.exists():
        AUTH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        config = _create_default_config()
        with open(AUTH_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return config
    with open(AUTH_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _create_default_config() -> dict:
    import secrets
    salt = secrets.token_hex(16)

    def _hash(pw):
        return hashlib.sha256(f"{salt}{pw}".encode()).hexdigest()

    return {
        "salt": salt,
        "users": [
            {"username": "admin", "password_hash": _hash("admin123"), "role": "admin", "display_name": "管理员"},
            {"username": "monitor", "password_hash": _hash("monitor123"), "role": "monitor", "display_name": "监测组"},
            {"username": "dispo", "password_hash": _hash("dispo123"), "role": "disposition", "display_name": "处置组"},
            {"username": "editor", "password_hash": _hash("editor123"), "role": "report_editor", "display_name": "日报编辑"},
        ],
    }


def authenticate(username: str, password: str) -> dict | None:
    config = _load_auth_config()
    salt = config.get("salt", "")
    pw_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    for user in config.get("users", []):
        if user["username"] == username and user["password_hash"] == pw_hash:
            return {
                "username": user["username"],
                "role": user["role"],
                "display_name": user.get("display_name", user["username"]),
            }
    return None


def get_allowed_tabs(role: str) -> list[str]:
    return ROLE_TABS.get(role, ["📚 知识库"])


def get_role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)
