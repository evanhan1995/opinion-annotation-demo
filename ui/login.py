# -*- coding: utf-8 -*-
"""Login page renderer for sentiment annotation system."""

import base64
import json
from pathlib import Path

import streamlit as st
from engine.auth import authenticate, get_allowed_tabs, get_role_label
from ui.theme import BRAND_COLORS

REMEMBERED_USER_PATH = Path(__file__).resolve().parent.parent / "config" / "remembered_user.json"


def _load_remembered_user() -> dict:
    """Load remembered username and password from disk."""
    if REMEMBERED_USER_PATH.exists():
        try:
            data = json.loads(REMEMBERED_USER_PATH.read_text(encoding="utf-8"))
            username = data.get("username", "")
            password = data.get("password", "")
            if password:
                try:
                    password = base64.b64decode(password.encode()).decode()
                except Exception:
                    password = ""
            return {"username": username, "password": password}
        except Exception:
            pass
    return {"username": "", "password": ""}


def _save_remembered_user(username: str, password: str = ""):
    """Save username and optionally password to disk."""
    REMEMBERED_USER_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"username": username}
    if password:
        payload["password"] = base64.b64encode(password.encode()).decode()
    REMEMBERED_USER_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clear_remembered_user():
    """Remove remembered user file."""
    if REMEMBERED_USER_PATH.exists():
        REMEMBERED_USER_PATH.unlink()


def _try_auto_login() -> bool:
    """Attempt auto-login with remembered credentials. Returns True on success."""
    remembered = _load_remembered_user()
    username = remembered["username"]
    password = remembered["password"]
    if not username or not password:
        return False

    user = authenticate(username, password)
    if user:
        st.session_state.authenticated = True
        st.session_state.user = user
        st.session_state.active_tab = get_allowed_tabs(user["role"])[0]
        return True

    # Password changed since last save — clear and fall through to form
    _clear_remembered_user()
    return False


def render_login_page():
    """Render a centered login form. Returns True if authenticated."""

    # Auto-login with remembered credentials
    if not st.session_state.get("authenticated"):
        if _try_auto_login():
            st.rerun()

    _, center, _ = st.columns([1, 2, 1])
    remembered = _load_remembered_user()

    with center:
        st.markdown(
            f"<h1 style='text-align:center;color:{BRAND_COLORS['primary']};"
            f"margin-bottom:0;border:none;'>sentiment intelligent annotation system</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#78909c;margin-bottom:1.5rem;'>"
            "Wiki KB + LLM intelligent labeling and triage</p>",
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="login-card">',
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='text-align:center;font-size:1.1rem;font-weight:600;"
            f"color:{BRAND_COLORS['text']};margin-bottom:1rem;'>user login</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input(
                "username", placeholder="enter username",
                value=remembered["username"],
                key="login_username",
            )
            password = st.text_input(
                "password", type="password", placeholder="enter password",
                value=remembered["password"],
                key="login_password",
            )

            col1, col2 = st.columns(2)
            with col1:
                remember_user = st.checkbox("remember username", value=bool(remembered["username"]), key="login_remember")
            with col2:
                remember_pass = st.checkbox("remember password", value=bool(remembered["password"]), key="login_remember_pass")

            submitted = st.form_submit_button("login", type="primary", use_container_width=True)

            if submitted:
                if not username.strip() or not password.strip():
                    st.error("please enter username and password")
                else:
                    user = authenticate(username.strip(), password.strip())
                    if user:
                        if remember_user:
                            pwd = password.strip() if remember_pass else ""
                            _save_remembered_user(username.strip(), pwd)
                        else:
                            _clear_remembered_user()
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.active_tab = get_allowed_tabs(user["role"])[0]
                        st.rerun()
                    else:
                        st.error("wrong username or password")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            "<p style='text-align:center;font-size:0.8rem;color:#b0bec5;margin-top:1rem;'>"
            "test accounts: admin/admin123 | monitor/monitor123 | dispo/dispo123</p>",
            unsafe_allow_html=True,
        )

    return st.session_state.get("authenticated", False)


def render_logout_button():
    """Render logout button in sidebar with user info."""
    user = st.session_state.get("user", {})
    if user:
        role_label = get_role_label(user.get("role", ""))
        st.caption(f"{user.get('display_name', '?')} ({role_label})")

        if st.button("logout", use_container_width=True, key="logout_btn"):
            for key in list(st.session_state.keys()):
                if key in ("authenticated", "user", "active_tab"):
                    del st.session_state[key]
            st.rerun()
