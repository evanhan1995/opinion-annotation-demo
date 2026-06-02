# -*- coding: utf-8 -*-
"""Unified retry framework with exponential backoff + jitter.

Usage:
    from engine.retry import retry_call, RetryConfig, PermanentError

    result = retry_call(yt_dlp.extract_info, url, download=False,
                        config=RetryConfig(max_retries=2, base_delay=2.0))
"""
import io
import random
import sys
import time
from dataclasses import dataclass

import engine._compat


class PermanentError(Exception):
    """Non-retryable error — raised immediately without retry."""


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 2.0
    backoff: float = 2.0
    max_delay: float = 60.0
    jitter: bool = True


def retry_call(fn, *args, config=None, **kwargs):
    """Execute fn(*args, **kwargs) with exponential backoff + jitter.

    Only retries on transient errors. PermanentError is re-raised immediately.

    Args:
        fn: Callable to retry
        config: RetryConfig (uses defaults if None)
        _url: Optional URL context for error messages
        _platform: Optional platform name for error messages
        _stage: Optional stage name for error messages

    Returns:
        fn's return value on success.

    Raises:
        PermanentError: immediately, without retry.
        Last exception: after all retries exhausted.
    """
    if config is None:
        config = RetryConfig()

    # Extract context kwargs (not passed to fn)
    _url = kwargs.pop("_url", "")
    _platform = kwargs.pop("_platform", "")
    _stage = kwargs.pop("_stage", "")

    last_err = None
    delay = config.base_delay

    for attempt in range(config.max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except PermanentError:
            raise
        except Exception as e:
            last_err = e
            if attempt < config.max_retries:
                actual_delay = delay
                if config.jitter:
                    actual_delay = delay * (0.5 + random.random())
                ctx = f"[{_platform}][{_stage}]" if _platform else ""
                print(f"{ctx} Retry {attempt+1}/{config.max_retries} after {actual_delay:.1f}s: {e}",
                      file=sys.stderr)
                time.sleep(actual_delay)
                delay = min(delay * config.backoff, config.max_delay)

    raise last_err
