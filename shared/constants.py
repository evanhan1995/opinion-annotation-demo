# -*- coding: utf-8 -*-
"""Shared constants for the opinion annotation system.

Re-exports PLATFORM_ABBREV from engine/constants.py for backward compatibility.
"""

from engine.constants import PLATFORM_ABBREV, PLATFORM_KEY_TO_LABEL, PLATFORM_LABEL_TO_KEY

__all__ = ["PLATFORM_ABBREV", "PLATFORM_KEY_TO_LABEL", "PLATFORM_LABEL_TO_KEY"]
