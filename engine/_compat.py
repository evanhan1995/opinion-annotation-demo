# -*- coding: utf-8 -*-
"""Windows UTF-8 terminal adapter — import once, replaces 3-line snippet everywhere."""
import io
import sys

def _ensure_utf8():
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "buffer"):
        if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_ensure_utf8()
