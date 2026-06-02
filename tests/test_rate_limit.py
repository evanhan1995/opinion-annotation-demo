# -*- coding: utf-8 -*-
"""Tests for engine.ratelimit — token bucket rate limiter."""
import io
import sys
import threading
import time
import pytest
from engine.ratelimit import RateLimiter, get_limiter

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class TestRateLimiter:
    """Token bucket behavior."""

    def test_initial_acquire_succeeds(self):
        rl = RateLimiter(rate=10.0, capacity=5.0)
        for _ in range(5):
            assert rl.acquire(timeout=0.1)

    def test_burst_exhausts_tokens(self):
        rl = RateLimiter(rate=0.1, capacity=1.0)  # 1 token every 10s
        assert rl.acquire(timeout=0.1)  # initial token
        assert not rl.acquire(timeout=0.1)  # no refill yet

    def test_refill_over_time(self):
        rl = RateLimiter(rate=10.0, capacity=1.0)  # 10 tokens/s, 1 token per 100ms
        assert rl.acquire(timeout=0.1)
        assert not rl.acquire(timeout=0.001)  # not enough time (1ms << 100ms needed)
        time.sleep(0.15)  # wait for ~1.5 tokens to refill
        assert rl.acquire(timeout=0.1)

    def test_timeout_returns_false(self):
        rl = RateLimiter(rate=0.01, capacity=1.0)  # 1 token every 100s
        rl.acquire(timeout=0.1)  # consume the only token
        start = time.monotonic()
        result = rl.acquire(timeout=0.1)
        elapsed = time.monotonic() - start
        assert result is False
        assert elapsed < 0.5  # should return quickly

    def test_does_not_exceed_capacity(self):
        rl = RateLimiter(rate=0.01, capacity=3.0)  # extremely slow refill
        # No sleep — initial capacity is 3
        acquired = 0
        while rl.acquire(timeout=0.01):
            acquired += 1
        assert acquired <= 3  # should not exceed initial capacity

    def test_thread_safety(self):
        rl = RateLimiter(rate=0.01, capacity=20.0)
        # No sleep — initial capacity is 20
        results = []
        lock = threading.Lock()

        def worker():
            local_acq = 0
            while rl.acquire(timeout=0.01):
                local_acq += 1
            with lock:
                results.append(local_acq)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total = sum(results)
        assert total <= 20  # capacity not exceeded across threads


class TestGetLimiter:
    """Per-platform limiter registry."""

    def test_returns_same_instance(self):
        a = get_limiter("xhs")
        b = get_limiter("xhs")
        assert a is b

    def test_case_insensitive(self):
        a = get_limiter("XHS")
        b = get_limiter("xhs")
        assert a is b

    def test_different_platforms_different_instances(self):
        a = get_limiter("xhs")
        b = get_limiter("youtube")
        assert a is not b

    def test_unknown_platform_gets_default(self):
        rl = get_limiter("nonexistent")
        assert isinstance(rl, RateLimiter)
