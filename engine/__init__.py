# -*- coding: utf-8 -*-
"""Engine package — shared infra for all agents.

Exports:
  ENGINE_DIR  — absolute Path to engine/ directory
  get_path    — resolve external tool paths (env var → config.json → default)
"""

import json
import os as _os
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent


def get_path(key: str, default: str = "") -> str:
    """Resolve an external tool path.

    Resolution order:
      1. Environment variable (key uppercased, e.g. "xhs_downloader" → XHS_DOWNLOADER)
      2. engine/config.json paths section
      3. Caller-supplied default

    Usage:
        from engine import get_path
        xhs_dir = get_path("xhs_downloader", "D:/tools/XHS-Downloader")
    """
    # 1. Environment variable
    env_key = key.upper()
    env_val = _os.environ.get(env_key, "")
    if env_val:
        return env_val

    # 2. config.json paths section
    config_path = ENGINE_DIR / "config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            paths = cfg.get("paths", {})
            if key in paths and paths[key]:
                return paths[key]
        except (json.JSONDecodeError, OSError):
            pass

    return default
