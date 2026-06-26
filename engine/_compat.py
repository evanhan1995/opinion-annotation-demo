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


# ── Timeout wrapper (shared by all agents and engine) ───────────────────
import concurrent.futures as _futures


def call_with_timeout(fn, timeout: float, *args, **kwargs):
    """Run fn(*args, **kwargs) in a thread with hard wall-clock timeout.

    Returns (result, None) on success, (None, error_string) on timeout/exception.
    Uses a fresh single-worker executor per call — no shared pool, no thread leak.
    """
    executor = _futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = executor.submit(fn, *args, **kwargs)
        return fut.result(timeout=timeout), None
    except _futures.TimeoutError:
        return None, f"操作超时 ({timeout}s)"
    except Exception as e:
        return None, str(e)
    finally:
        executor.shutdown(wait=False)
