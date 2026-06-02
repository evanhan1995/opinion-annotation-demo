# -*- coding: utf-8 -*-
"""Token bucket rate limiter with per-platform instances.

Usage:
    from engine.ratelimit import RateLimiter, get_limiter

    limiter = get_limiter("xhs")       # 1 req/s
    if not limiter.acquire(timeout=30):
        raise TimeoutError("Rate limit wait exceeded")
"""
import io
import sys
import threading
import time

import engine._compat

# Per-platform rate limits (requests per second)
_PLATFORM_RATES: dict[str, float] = {
    "xhs": 0.3,
    "douyin": 2.0,
    "youtube": 5.0,
    "bilibili": 3.0,
    "weibo": 2.0,
    "wechat": 1.0,
    "x": 1.0,
    "reddit": 2.0,
    "generic": 5.0,
}


class RateLimiter:
    """Token bucket rate limiter.

    Thread-safe. Tokens refill at rate tokens/sec up to capacity.
    """

    def __init__(self, rate: float = 1.0, capacity: float = 3.0):
        self.rate = rate          # tokens per second
        self.capacity = capacity  # max burst
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def acquire(self, timeout: float = 30.0) -> bool:
        """Block until a token is available. Returns False on timeout."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                # Calculate wait time for next token
                wait = (1.0 - self._tokens) / self.rate
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(wait, max(remaining, 0.01)))


# Global limiter registry
_limiters: dict[str, RateLimiter] = {}
_registry_lock = threading.Lock()


def get_limiter(platform: str) -> RateLimiter:
    """Get or create a rate limiter for the given platform key."""
    key = platform.lower()
    with _registry_lock:
        if key not in _limiters:
            rate = _PLATFORM_RATES.get(key, 5.0)
            _limiters[key] = RateLimiter(rate=rate)
        return _limiters[key]
