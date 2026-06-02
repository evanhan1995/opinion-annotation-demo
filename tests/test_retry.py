# -*- coding: utf-8 -*-
"""Tests for engine.retry — unified retry framework."""
import io
import sys
import time
import pytest
from engine.retry import retry_call, RetryConfig, PermanentError

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class TestRetryCall:
    """Core retry behavior."""

    def test_success_first_attempt(self):
        call_count = [0]

        def fn():
            call_count[0] += 1
            return "ok"

        result = retry_call(fn, config=RetryConfig(max_retries=3, base_delay=0.01))
        assert result == "ok"
        assert call_count[0] == 1

    def test_retry_on_transient_error(self):
        call_count = [0]

        def fn():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = retry_call(fn, config=RetryConfig(max_retries=3, base_delay=0.01, jitter=False))
        assert result == "recovered"
        assert call_count[0] == 3

    def test_exhaust_retries(self):
        call_count = [0]

        def fn():
            call_count[0] += 1
            raise ConnectionError("persistent")

        with pytest.raises(ConnectionError, match="persistent"):
            retry_call(fn, config=RetryConfig(max_retries=2, base_delay=0.01, jitter=False))
        assert call_count[0] == 3  # initial + 2 retries

    def test_permanent_error_not_retried(self):
        call_count = [0]

        def fn():
            call_count[0] += 1
            raise PermanentError("fatal")

        with pytest.raises(PermanentError, match="fatal"):
            retry_call(fn, config=RetryConfig(max_retries=3, base_delay=0.01))
        assert call_count[0] == 1

    def test_zero_retries(self):
        call_count = [0]

        def fn():
            call_count[0] += 1
            raise ValueError("fail")

        with pytest.raises(ValueError, match="fail"):
            retry_call(fn, config=RetryConfig(max_retries=0, base_delay=0.01))
        assert call_count[0] == 1

    def test_passes_args_and_kwargs(self):
        def fn(a, b=0):
            return a + b

        result = retry_call(fn, 3, b=4)
        assert result == 7

    def test_context_kwargs_not_passed_to_fn(self):
        def fn(x):
            return x

        result = retry_call(fn, 42, _platform="test", _stage="s1", _url="http://x")
        assert result == 42

    def test_exponential_backoff_delay(self):
        """Verify that delay doubles between retries (no jitter)."""
        delays = []
        original_sleep = time.sleep

        def fake_sleep(d):
            delays.append(d)

        time.sleep = fake_sleep
        call_count = [0]

        def fn():
            call_count[0] += 1
            raise ConnectionError("fail")

        try:
            with pytest.raises(ConnectionError):
                retry_call(fn, config=RetryConfig(max_retries=2, base_delay=1.0, jitter=False))
        finally:
            time.sleep = original_sleep

        assert len(delays) == 2
        assert abs(delays[0] - 1.0) < 0.01
        assert abs(delays[1] - 2.0) < 0.01

    def test_max_delay_cap(self):
        delays = []
        original_sleep = time.sleep

        def fake_sleep(d):
            delays.append(d)

        time.sleep = fake_sleep
        call_count = [0]

        def fn():
            call_count[0] += 1
            raise ConnectionError("fail")

        try:
            with pytest.raises(ConnectionError):
                retry_call(fn, config=RetryConfig(
                    max_retries=4, base_delay=10.0, max_delay=25.0, jitter=False))
        finally:
            time.sleep = original_sleep

        # Delays should be: 10, 20, 25 (capped), 25 (capped)
        assert delays[0] == 10.0
        assert delays[1] == 20.0
        assert all(d <= 26.0 for d in delays)
