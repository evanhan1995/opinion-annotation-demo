# -*- coding: utf-8 -*-
"""Authentication tests — verify no default accounts, PBKDF2 hashing, login flow."""

import os
import sys
from pathlib import Path
import pytest


def _get_auth_with_path(config_dir):
    """Import auth module with AUTH_CONFIG_PATH pointing to config_dir/auth_config.json."""
    config_path = Path(config_dir) / "auth_config.json"
    # Purge cached auth module to get a clean import
    for key in list(sys.modules.keys()):
        if key == "engine.auth" or key.startswith("engine.auth."):
            del sys.modules[key]
    import engine.auth
    engine.auth.AUTH_CONFIG_PATH = config_path
    # Delete existing file if any
    if config_path.exists():
        config_path.unlink()
    return engine.auth


class TestAuthDefaults:

    def test_no_default_accounts(self, tmp_path):
        """Without INIT_ADMIN_PASSWORD, config should have zero users."""
        old_env = os.environ.pop("INIT_ADMIN_PASSWORD", None)
        try:
            auth = _get_auth_with_path(tmp_path)
            cfg = auth._load_auth_config()
            assert len(cfg["users"]) == 0
        finally:
            if old_env:
                os.environ["INIT_ADMIN_PASSWORD"] = old_env

    def test_authenticate_without_config(self, tmp_path):
        """authenticate() must return None when no config exists."""
        old_env = os.environ.pop("INIT_ADMIN_PASSWORD", None)
        try:
            auth = _get_auth_with_path(tmp_path)
            assert auth.authenticate("admin", "admin123") is None
        finally:
            if old_env:
                os.environ["INIT_ADMIN_PASSWORD"] = old_env

    def test_admin_from_env_var(self, tmp_path):
        """INIT_ADMIN_PASSWORD creates a single admin account."""
        old_env = os.environ.pop("INIT_ADMIN_PASSWORD", None)
        os.environ["INIT_ADMIN_PASSWORD"] = "TestP@ssw0rd!"
        try:
            auth = _get_auth_with_path(tmp_path)
            cfg = auth._load_auth_config()
            assert len(cfg["users"]) == 1
            assert cfg["users"][0]["username"] == "admin"
            result = auth.authenticate("admin", "TestP@ssw0rd!")
            assert result is not None
            assert result["role"] == "admin"
        finally:
            if old_env:
                os.environ["INIT_ADMIN_PASSWORD"] = old_env
            else:
                del os.environ["INIT_ADMIN_PASSWORD"]

    def test_wrong_password_rejected(self, tmp_path):
        """Wrong password must return None."""
        old_env = os.environ.pop("INIT_ADMIN_PASSWORD", None)
        os.environ["INIT_ADMIN_PASSWORD"] = "CorrectP@ss1"
        try:
            auth = _get_auth_with_path(tmp_path)
            assert auth.authenticate("admin", "WrongPassword") is None
        finally:
            if old_env:
                os.environ["INIT_ADMIN_PASSWORD"] = old_env
            else:
                del os.environ["INIT_ADMIN_PASSWORD"]

    def test_pbkdf2_hash_format(self, tmp_path):
        """Password hash must be 64 hex chars (PBKDF2-SHA256 output)."""
        old_env = os.environ.pop("INIT_ADMIN_PASSWORD", None)
        os.environ["INIT_ADMIN_PASSWORD"] = "HashTest1!"
        try:
            auth = _get_auth_with_path(tmp_path)
            cfg = auth._load_auth_config()
            pw_hash = cfg["users"][0]["password_hash"]
            assert len(pw_hash) == 64
        finally:
            if old_env:
                os.environ["INIT_ADMIN_PASSWORD"] = old_env
            else:
                del os.environ["INIT_ADMIN_PASSWORD"]

    def test_salt_is_random(self, tmp_path):
        """Two config generations must produce different salts."""
        old_env = os.environ.pop("INIT_ADMIN_PASSWORD", None)
        os.environ["INIT_ADMIN_PASSWORD"] = "SaltTest1!"
        try:
            auth1 = _get_auth_with_path(tmp_path)
            salt1 = auth1._load_auth_config()["salt"]

            # New temp path = fresh config
            tmp2 = tmp_path / "sub"
            tmp2.mkdir()
            auth2 = _get_auth_with_path(tmp2)
            salt2 = auth2._load_auth_config()["salt"]

            assert salt1 != salt2
        finally:
            if old_env:
                os.environ["INIT_ADMIN_PASSWORD"] = old_env
            else:
                del os.environ["INIT_ADMIN_PASSWORD"]


class TestRoleAccess:

    def test_admin_has_all_tabs(self):
        from engine.auth import get_allowed_tabs
        assert len(get_allowed_tabs("admin")) == 8

    def test_monitor_limited_tabs(self):
        from engine.auth import get_allowed_tabs
        assert len(get_allowed_tabs("monitor")) == 4

    def test_unknown_role_defaults(self):
        from engine.auth import get_allowed_tabs
        assert len(get_allowed_tabs("nonexistent")) == 1
