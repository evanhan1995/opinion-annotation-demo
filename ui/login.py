# -*- coding: utf-8 -*-
"""Login page renderer for 舆情标注系统."""

import json
from pathlib import Path

import streamlit as st
from engine.auth import authenticate, get_allowed_tabs, get_role_label
from ui.theme import BRAND_COLORS

REMEMBERED_USER_PATH = Path(__file__).resolve().parent.parent / "config" / "remembered_user.json"


def _load_remembered_user() -> str:
    """Load remembered username from disk."""
    if REMEMBERED_USER_PATH.exists():
        try:
            data = json.loads(REMEMBERED_USER_PATH.read_text(encoding="utf-8"))
            return data.get("username", "")
        except Exception:
            return ""
    return ""


def _save_remembered_user(username: str):
    """Save username to disk for next login."""
    REMEMBERED_USER_PATH.parent.mkdir(parents=True, exist_ok=True)
    REMEMBERED_USER_PATH.write_text(
        json.dumps({"username": username}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clear_remembered_user():
    """Remove remembered username file."""
    if REMEMBERED_USER_PATH.exists():
        REMEMBERED_USER_PATH.unlink()


def render_login_page():
    """Render a centered login form. Returns True if authenticated."""

    _, center, _ = st.columns([1, 2, 1])
    remembered = _load_remembered_user()

    with center:
        st.markdown(
            f"<h1 style='text-align:center;color:{BRAND_COLORS['primary']};"
            f"margin-bottom:0;border:none;'>舆情智能标注系统</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#78909c;margin-bottom:1.5rem;'>"
            "基于 Wiki 知识库 + LLM 的智能打标与分流判断</p>",
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="login-card">',
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='text-align:center;font-size:1.1rem;font-weight:600;"
            f"color:{BRAND_COLORS['text']};margin-bottom:1rem;'>用户登录</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input(
                "用户名", placeholder="请输入用户名",
                value=remembered,
                key="login_username",
            )
            password = st.text_input(
                "密码", type="password", placeholder="请输入密码",
                key="login_password",
            )
            remember = st.checkbox("记住账号", value=bool(remembered), key="login_remember")
            submitted = st.form_submit_button("登录", type="primary", use_container_width=True)

            if submitted:
                if not username.strip() or not password.strip():
                    st.error("请输入用户名和密码")
                else:
                    user = authenticate(username.strip(), password.strip())
                    if user:
                        if remember:
                            _save_remembered_user(username.strip())
                        else:
                            _clear_remembered_user()
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.active_tab = get_allowed_tabs(user["role"])[0]
                        st.rerun()
                    else:
                        st.error("用户名或密码错误")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            "<p style='text-align:center;font-size:0.8rem;color:#b0bec5;margin-top:1rem;'>"
            "测试账号: admin/admin123 | monitor/monitor123 | dispo/dispo123</p>",
            unsafe_allow_html=True,
        )

    return st.session_state.get("authenticated", False)


def render_logout_button():
    """Render logout button in sidebar with user info."""
    user = st.session_state.get("user", {})
    if user:
        role_label = get_role_label(user.get("role", ""))
        st.caption(f"{user.get('display_name', '?')} ({role_label})")

        if st.button("🚪 退出登录", use_container_width=True, key="logout_btn"):
            for key in list(st.session_state.keys()):
                if key in ("authenticated", "user", "active_tab"):
                    del st.session_state[key]
            st.rerun()
