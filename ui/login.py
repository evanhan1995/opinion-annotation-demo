# -*- coding: utf-8 -*-
"""Login page renderer for sentiment annotation system — Figma 1:1 design."""

import base64
import json
from pathlib import Path

import streamlit as st
from engine.auth import authenticate, get_allowed_tabs, get_role_label

REMEMBERED_USER_PATH = Path(__file__).resolve().parent.parent / "config" / "remembered_user.json"
LOGOUT_FLAG_PATH = REMEMBERED_USER_PATH.parent / ".logout_flag"
SESSION_FILE = REMEMBERED_USER_PATH.parent / ".session_active"


def _load_remembered_user() -> dict:
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
    REMEMBERED_USER_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"username": username}
    if password:
        payload["password"] = base64.b64encode(password.encode()).decode()
    REMEMBERED_USER_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clear_remembered_user():
    if REMEMBERED_USER_PATH.exists():
        REMEMBERED_USER_PATH.unlink()


def _try_auto_login() -> bool:
    import datetime as _dt
    def _dlog(msg):
        try:
            with open(REMEMBERED_USER_PATH.parent / "_debug.log", "a", encoding="utf-8") as _f:
                _f.write(f"{_dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]} AUTO_LOGIN: {msg}\n")
        except Exception:
            pass
    remembered = _load_remembered_user()
    username = remembered["username"]
    password = remembered["password"]
    _dlog(f"loaded user='{username}' has_pwd={bool(password)}")
    if not username or not password:
        _dlog("no stored credentials → skip")
        return False
    user = authenticate(username, password)
    if user:
        _dlog(f"auth succeeded for '{username}', setting session")
        # Refresh session persistence file
        import time as _time2
        SESSION_FILE.write_text(json.dumps({
            "username": user["username"],
            "role": user["role"],
            "display_name": user.get("display_name", user["username"]),
            "timestamp": _time2.time(),
        }, ensure_ascii=False), encoding="utf-8")
        st.session_state.authenticated = True
        st.session_state.user = user
        st.session_state.active_tab = get_allowed_tabs(user["role"])[0]
        return True
    _dlog("auth failed → clearing remembered file")
    _clear_remembered_user()
    return False


def _inject_login_css():
    """Inject login-page CSS — styling only, layout is handled by st.columns."""
    st.markdown("""<style>
    /* ── Page reset ── */
    .stApp {
        background: #EFF1F5 !important;
    }
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    /* Remove Streamlit default padding from main + columns */
    .main > div, .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        max-width: none !important;
    }
    div[data-testid="column"] {
        padding: 0 !important;
    }

    /* ── Blue left panel ── */
    .login-brand {
        background: #0D47A1;
        min-height: 100vh;
        display: flex; flex-direction: column; justify-content: center;
        padding: 80px 64px;
        box-sizing: border-box;
    }
    .login-brand h1 {
        font-family: "Noto Sans SC", sans-serif;
        font-size: 36px; font-weight: 700; color: #fff;
        margin: 0 0 12px 0; padding: 0; border: none;
        letter-spacing: 0; line-height: 1.2;
    }
    .login-brand .sub {
        font-family: "Inter", sans-serif;
        font-size: 14px; font-weight: 400;
        color: rgba(255,255,255,0.85); margin: 0 0 40px 0;
    }
    .login-brand .line {
        width: 60px; height: 2px;
        background: rgba(255,255,255,0.4); margin-bottom: 20px;
    }
    .login-brand .desc {
        font-family: "Noto Sans SC", sans-serif;
        font-size: 14px; font-weight: 400;
        color: rgba(255,255,255,0.7); margin: 0 0 60px 0;
    }
    .login-brand .features {
        list-style: none; padding: 0; margin: 0;
        display: flex; flex-direction: column; gap: 24px;
    }
    .login-brand .features li {
        display: flex; align-items: center; gap: 10px;
        font-family: "Noto Sans SC", sans-serif;
        font-size: 13px; color: rgba(255,255,255,0.75);
    }
    .login-brand .features li span {
        font-size: 18px; width: 24px; text-align: center;
    }

    /* ── Login card (the stForm) ── */
    div[data-testid="stForm"] {
        width: 420px !important;
        max-width: 100% !important;
        background: #fff !important;
        border-radius: 12px !important;
        border-top: 3px solid #0D47A1 !important;
        padding: 36px 36px 28px 36px !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.06) !important;
        margin: 20vh auto 32px auto !important;
    }
    .login-card-title {
        font-family: "Noto Sans SC", sans-serif !important;
        font-size: 22px !important; font-weight: 500 !important;
        color: #1A1A2E !important; text-align: center !important;
        margin: 0 0 20px 0 !important; padding: 0 !important;
    }

    /* ── Form elements ── */
    div[data-testid="stForm"] label {
        font-family: "Noto Sans SC", sans-serif !important;
        font-size: 14px !important; font-weight: 500 !important;
        color: #1A1A2E !important;
    }
    div[data-testid="stForm"] input[type="text"],
    div[data-testid="stForm"] input[type="password"] {
        height: 44px !important;
        background: #F7F9FA !important;
        border: 1px solid #E2E8EF !important;
        border-radius: 8px !important;
        font-size: 14px !important;
        color: #1A1A2E !important;
        padding: 0 16px !important;
    }
    div[data-testid="stForm"] input:focus {
        border-color: #0D47A1 !important;
        box-shadow: 0 0 0 2px rgba(13,71,161,0.12) !important;
    }
    div[data-testid="stForm"] div[data-testid="stCheckbox"] label {
        font-size: 13px !important; font-weight: 400 !important;
    }

    /* ── Button ── */
    div[data-testid="stForm"] .stButton > button {
        width: 100% !important; height: 44px !important;
        background: #0D47A1 !important; color: #fff !important;
        border: none !important; border-radius: 8px !important;
        font-family: "Noto Sans SC", sans-serif !important;
        font-size: 16px !important; font-weight: 500 !important;
    }
    div[data-testid="stForm"] .stButton > button:hover {
        background: #1565C0 !important; transform: translateY(-1px);
        box-shadow: 0 3px 8px rgba(13,71,161,0.25) !important;
    }
    div[data-testid="stForm"] .stAlert {
        border-radius: 8px; border-left-width: 4px;
    }

    /* ── Footer ── */
    .login-footer {
        text-align: center;
        font-family: "Noto Sans SC", sans-serif;
        font-size: 12px; color: #A0B0C7;
    }
    </style>""", unsafe_allow_html=True)


def render_login_page():
    """Render a login page matching Figma design. Returns True if authenticated."""
    import datetime as _dt
    try:
        with open(REMEMBERED_USER_PATH.parent / "_debug.log", "a", encoding="utf-8") as _f:
            _f.write(f"{_dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]} LOGIN_PAGE: render called, auth={st.session_state.get('authenticated', 'MISSING')}\n")
    except Exception:
        pass

    if not st.session_state.get("authenticated"):
        if _try_auto_login():
            st.rerun()

    remembered = _load_remembered_user()
    _inject_login_css()

    # ── Layout: left blue panel + right login area ──
    # Proportions 5:7 ≈ 520:920 at 1440px viewport
    left, right = st.columns([5, 7], gap="small")

    with left:
        st.html(
            '<div class="login-brand">'
            '<h1>舆情智能标注系统</h1>'
            '<p class="sub">Sentiment Intelligent Annotation System</p>'
            '<div class="line"></div>'
            '<p class="desc">基于 Wiki 知识库 + LLM 的智能打标与分流判断</p>'
            '<ul class="features">'
            '<li><span>📊</span>总览仪表板</li>'
            '<li><span>📡</span>Monitor 巡检</li>'
            '<li><span>📝</span>录入研判</li>'
            '<li><span>📚</span>知识库</li>'
            '</ul>'
            '</div>'
        )

    with right:
        with st.form("login_form"):
            st.markdown('<p class="login-card-title">用户登录</p>', unsafe_allow_html=True)

            username = st.text_input(
                "用户名", placeholder="请输入用户名",
                value=remembered["username"],
                key="login_username",
            )
            password = st.text_input(
                "密码", type="password", placeholder="请输入密码",
                value=remembered["password"],
                key="login_password",
            )

            remember_user = st.checkbox(
                "记住用户名", value=bool(remembered["username"]),
                key="login_remember",
            )

            submitted = st.form_submit_button("登录", type="primary", use_container_width=True)

            if submitted:
                if not username.strip() or not password.strip():
                    st.error("请输入用户名和密码")
                else:
                    user = authenticate(username.strip(), password.strip())
                    if user:
                        if remember_user:
                            _save_remembered_user(username.strip(), password.strip())
                        else:
                            _clear_remembered_user()
                        # Session persistence: survives full-page navigation (tab links)
                        import time as _time3, traceback as _tb
                        _payload = json.dumps({
                            "username": user["username"],
                            "role": user["role"],
                            "display_name": user.get("display_name", user["username"]),
                            "timestamp": _time3.time(),
                        }, ensure_ascii=False)
                        try:
                            SESSION_FILE.write_text(_payload, encoding="utf-8")
                            with open(REMEMBERED_USER_PATH.parent / "_debug.log", "a", encoding="utf-8") as _f:
                                _f.write(f"{_dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]} LOGIN_FORM: session file written OK\n")
                        except Exception as _e:
                            with open(REMEMBERED_USER_PATH.parent / "_debug.log", "a", encoding="utf-8") as _f:
                                _f.write(f"{_dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]} LOGIN_FORM: session file WRITE FAILED: {_e}\n{_tb.format_exc()}\n")
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.active_tab = get_allowed_tabs(user["role"])[0]
                        st.rerun()
                    else:
                        st.error("用户名或密码错误")

        st.markdown(
            '<p class="login-footer">舆情智能标注系统 | 基于 Wiki 知识库 + 案例驱动迭代</p>',
            unsafe_allow_html=True,
        )

    return st.session_state.get("authenticated", False)


def render_logout_button():
    """Render logout button in sidebar. Clears credentials + auth session."""
    import datetime as _dt
    def _dlog(msg):
        try:
            with open(REMEMBERED_USER_PATH.parent / "_debug.log", "a", encoding="utf-8") as _f:
                _f.write(f"{_dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]} {msg}\n")
        except Exception:
            pass

    if st.button("退出登录", use_container_width=True, key="logout_btn"):
        _dlog("BUTTON CLICKED — starting logout")
        _clear_remembered_user()
        # Delete session persistence file
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
        _dlog(f"  creds file deleted, exists now: {REMEMBERED_USER_PATH.exists()}")
        for _k in ("authenticated", "user", "active_tab"):
            st.session_state.pop(_k, None)
        _dlog(f"  session keys popped, auth now: {st.session_state.get('authenticated', 'MISSING')}")
        _dlog("  calling st.rerun()")
        st.rerun()
