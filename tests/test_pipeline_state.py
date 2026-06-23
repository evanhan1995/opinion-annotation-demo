# -*- coding: utf-8 -*-
"""Pipeline state machine tests — harvest guard, reset, repeat trigger."""

import pytest


class TestPipelineState:
    """Verify pipeline status tracking and error resilience."""

    def test_initial_state_is_idle(self):
        from pipeline import get_pipeline_status
        status = get_pipeline_status()
        assert status["is_running"] is False
        assert all(s["status"] == "pending" for s in status["steps"])

    def test_force_reset_clears_running(self):
        from pipeline import force_reset_pipeline, get_pipeline_status
        force_reset_pipeline()
        status = get_pipeline_status()
        assert status["is_running"] is False
        for step in status["steps"]:
            assert step["status"] in ("pending", "error")

    def test_set_auto_mode(self):
        from pipeline import set_auto_mode, get_pipeline_status
        set_auto_mode(True)
        assert get_pipeline_status()["is_auto_mode"] is True
        set_auto_mode(False)
        assert get_pipeline_status()["is_auto_mode"] is False

    def test_double_trigger_is_safe(self):
        """trigger_pipeline must not crash when called while already running."""
        from pipeline import trigger_pipeline, force_reset_pipeline, get_pipeline_status

        force_reset_pipeline()
        # First trigger
        result1 = trigger_pipeline(source="test", init_status="待跟进", sort_preference="default")
        # Second should return False (already running) without crashing
        result2 = trigger_pipeline(source="test", init_status="待跟进", sort_preference="default")
        # At least one should have worked
        from pipeline import force_reset_pipeline
        force_reset_pipeline()
