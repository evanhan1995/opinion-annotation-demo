# -*- coding: utf-8 -*-
"""Tab: Settings — API config, KB password, Feishu webhook management."""

import json
import streamlit as st
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "engine" / "config.json"
NOTIF_PATH = PROJECT_ROOT / "notification_config.json"

PROVIDER_OPTIONS = ["deepseek", "ark", "minimax", "openai"]

PROVIDER_DEFAULTS = {
    "deepseek": {"api_base": "https://api.deepseek.com", "model": "deepseek-chat"},
    "ark": {"api_base": "https://ark.cn-beijing.volces.com/api/v3", "model": "deepseek-r1-250528"},
    "minimax": {"api_base": "https://api.minimax.chat/v1", "model": "abab7-chat"},
    "openai": {"api_base": "https://api.openai.com/v1", "model": "gpt-4o"},
}


def _load_engine_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def _save_engine_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_notif_config() -> dict:
    if NOTIF_PATH.exists():
        return json.loads(NOTIF_PATH.read_text(encoding="utf-8"))
    return {"desktop_alert": True, "webhooks": []}


def _save_notif_config(cfg: dict):
    NOTIF_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def render_tab_settings():
    """Render the Settings configuration tab."""
    st.subheader("⚙️ 系统设置")
    st.caption("配置 API 密钥、飞书通知 Webhook 等。修改后点击保存即时生效。")

    engine_cfg = _load_engine_config()
    notif_cfg = _load_notif_config()

    # ── Section 1: API Configuration ───────────────────────────────
    st.markdown("**🔑 API 配置**")

    provider = st.selectbox(
        "Provider", PROVIDER_OPTIONS,
        index=PROVIDER_OPTIONS.index(engine_cfg.get("provider", "deepseek"))
        if engine_cfg.get("provider", "deepseek") in PROVIDER_OPTIONS else 0,
        key="settings_provider",
    )

    api_key = st.text_input(
        "API Key", type="password",
        value=engine_cfg.get("api_key", ""),
        key="settings_api_key",
        placeholder="sk-...",
    )

    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["deepseek"])
    api_base = st.text_input(
        "API Base URL",
        value=engine_cfg.get("api_base", defaults["api_base"]),
        key="settings_api_base",
    )

    model = st.text_input(
        "Model",
        value=engine_cfg.get("model", defaults["model"]),
        key="settings_model",
    )

    c1, c2 = st.columns(2)
    with c1:
        max_tokens = st.number_input(
            "Max Tokens", min_value=256, max_value=16384, step=256,
            value=engine_cfg.get("max_tokens", 4096),
            key="settings_max_tokens",
        )
    with c2:
        temperature = st.slider(
            "Temperature", min_value=0.0, max_value=2.0, step=0.05,
            value=engine_cfg.get("temperature", 0.1),
            key="settings_temperature",
        )

    # ── Section 2: KB Password ────────────────────────────────────
    st.divider()
    st.markdown("**🔒 知识库密码**")
    kb_password = st.text_input(
        "KB Password", type="password",
        value=engine_cfg.get("kb_password", ""),
        key="settings_kb_password",
        placeholder="设置知识库访问密码（留空则不启用密码保护）",
    )

    # ── Section 3: WeChat Official Account ──────────────────────────
    st.divider()
    st.markdown("**💬 微信公众号配置**")
    st.caption("配置公众号后台 Cookie 以启用微信公众号文章搜索。前往 mp.weixin.qq.com 登录后从浏览器开发者工具获取。")

    wechat_cfg = engine_cfg.get("wechat", {})
    wechat_cookie = st.text_area(
        "公众号后台 Cookie",
        value=wechat_cfg.get("cookie", ""),
        key="settings_wechat_cookie",
        placeholder="从 mp.weixin.qq.com 浏览器开发者工具 → Network → 任意请求 → Request Headers → Cookie 复制",
        height=80,
    )
    wechat_token = st.text_input(
        "AppMsg Token",
        value=wechat_cfg.get("appmsg_token", ""),
        key="settings_wechat_token",
        placeholder="从微信文章页 URL 参数或抓包工具获取",
    )

    # ── Section 4: Feishu Notification ────────────────────────────
    st.divider()
    st.markdown("**📣 飞书通知**")

    desktop_alert = st.toggle(
        "桌面弹窗告警（Windows MessageBox）",
        value=notif_cfg.get("desktop_alert", True),
        key="settings_desktop_alert",
    )

    webhooks = notif_cfg.get("webhooks", [])
    if not webhooks:
        webhooks = [{"name": "", "url": "", "enabled": True, "trigger_level": "P0"}]

    for i, wh in enumerate(webhooks):
        with st.container():
            wh_name = st.text_input(
                "Webhook 名称", value=wh.get("name", ""),
                key=f"settings_wh_name_{i}",
                placeholder="例如: 飞书舆情告警群",
            )
            wh_url = st.text_input(
                "Webhook URL", value=wh.get("url", ""),
                key=f"settings_wh_url_{i}",
                placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/...",
                type="password",
            )
            cw1, cw2 = st.columns(2)
            with cw1:
                wh_trigger = st.selectbox(
                    "触发级别",
                    ["P0", "P0+P1"],
                    index=0 if wh.get("trigger_level", "P0") == "P0" else 1,
                    key=f"settings_wh_trigger_{i}",
                )
            with cw2:
                wh_enabled = st.toggle(
                    "启用", value=wh.get("enabled", True),
                    key=f"settings_wh_enabled_{i}",
                )

    # ── Save button ────────────────────────────────────────────────
    if st.button("💾 保存设置", type="primary", use_container_width=True, key="settings_save"):
        # Validate API key
        if not api_key.strip():
            st.error("API Key 不能为空")
            return

        new_engine = {
            "provider": provider,
            "api_key": api_key.strip(),
            "model": model.strip(),
            "api_base": api_base.strip(),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "kb_password": kb_password,
            "wechat": {
                "cookie": wechat_cookie.strip(),
                "appmsg_token": wechat_token.strip(),
            },
        }
        # Preserve unmanaged keys from existing config
        for k, v in engine_cfg.items():
            if k not in new_engine:
                new_engine[k] = v
        _save_engine_config(new_engine)

        new_notif = {
            "desktop_alert": desktop_alert,
            "webhooks": [],
        }
        for i in range(len(webhooks)):
            wh_name = st.session_state.get(f"settings_wh_name_{i}", "")
            wh_url = st.session_state.get(f"settings_wh_url_{i}", "")
            if wh_url.strip():
                new_notif["webhooks"].append({
                    "name": wh_name or f"Webhook {i+1}",
                    "url": wh_url.strip(),
                    "enabled": st.session_state.get(f"settings_wh_enabled_{i}", True),
                    "trigger_level": st.session_state.get(f"settings_wh_trigger_{i}", "P0"),
                })
        _save_notif_config(new_notif)

        # Update in-memory config so other tabs pick up changes immediately
        st.session_state.config = new_engine
        st.success("设置已保存！API Key 和通知配置已即时生效。")
