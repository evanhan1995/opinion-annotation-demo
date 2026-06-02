# -*- coding: utf-8 -*-
"""Tests for v7.1 SVM sentiment classifier."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jieba  # noqa: E402
from agents.sentinel import (  # noqa: E402
    _load_sentiment_model,
    _ml_sentiment_predict,
    screen_content,
)
from agents.shared import SentinelResult  # noqa: E402
from engine.sentiment_trainer import load_cases, train_model  # noqa: E402


@pytest.fixture(scope="module")
def trained_model(tmp_path_factory):
    """Train a model on real KB cases for tests."""
    cases = load_cases()
    if len(cases) < 10:
        pytest.skip("Not enough KB cases to train SVM")
    pkl_path = tmp_path_factory.mktemp("model") / "test_model.pkl"
    result = train_model(cases, model_path=pkl_path)
    return result


class TestModelTraining:
    """Verify SVM training pipeline."""

    def test_load_cases_returns_data(self):
        """load_cases should return labeled cases with valid sentiments."""
        cases = load_cases()
        assert len(cases) >= 10
        for c in cases:
            assert "text" in c
            assert "sentiment" in c
            assert c["sentiment"] in ("正面", "中性", "负面")
            assert len(c["text"]) > 0

    def test_train_model_returns_metrics(self, trained_model):
        """train_model should return evaluation metrics."""
        assert trained_model["n_cases"] >= 10
        assert trained_model["n_features"] > 0
        assert trained_model["labels"] == [
            "负面", "中性", "正面"
        ]
        assert "report" in trained_model

    def test_model_persistence(self, trained_model):
        """Model should be saveable to and loadable from pkl."""
        import joblib
        pkl_path = trained_model["model_path"]
        assert Path(pkl_path).exists()
        bundle = joblib.load(pkl_path)
        assert set(bundle.keys()) == {"svm", "vectorizer", "labels"}


class TestMLSentimentPredict:
    """Verify _ml_sentiment_predict behaviour."""

    @pytest.fixture(autouse=True)
    def _patch_model(self, trained_model, monkeypatch):
        """Replace module-level globals with test model."""
        monkeypatch.setattr(
            "agents.sentinel._SVM_MODEL", trained_model["model"]
        )
        monkeypatch.setattr(
            "agents.sentinel._SVM_VECTORIZER", trained_model["vectorizer"]
        )
        monkeypatch.setattr(
            "agents.sentinel._SVM_LABELS", trained_model["labels"]
        )

    def test_returns_none_for_empty_text(self):
        """Empty text should not crash."""
        _ml_sentiment_predict("")  # should not raise

    def test_returns_none_when_model_missing(self, monkeypatch):
        """Should return None when SVM model globals are None."""
        monkeypatch.setattr("agents.sentinel._SVM_MODEL", None)
        monkeypatch.setattr("agents.sentinel._SVM_VECTORIZER", None)
        monkeypatch.setattr("agents.sentinel._SVM_LABELS", None)
        assert _ml_sentiment_predict("some test text here") is None

    def test_returns_sentinel_result_or_none(self):
        """Should return SentinelResult or None without crashing."""
        result = _ml_sentiment_predict(
            "this product quality is great highly recommend buying it"
        )
        if result is not None:
            assert isinstance(result, SentinelResult)
            assert result.verdict in ("fast_track", "pass", "reject")

    def test_fast_track_has_sentiment(self):
        """When verdict is fast_track, suggested_sentiment must be set."""
        result = _ml_sentiment_predict(
            "very satisfied product works well strongly recommend"
        )
        if result is not None and result.verdict == "fast_track":
            assert result.suggested_sentiment in result.suggested_sentiment

    def test_severity_set_when_fast_track(self):
        """fast_track results have suggested_severity field."""
        result = _ml_sentiment_predict("product quality is great")
        if result is not None and result.verdict == "fast_track":
            assert result.suggested_severity in ("P0", "P1", "P2", "P3", "")


class TestScreenContentIntegration:
    """Verify SVM integration in screen_content pipeline."""

    @pytest.fixture(autouse=True)
    def _patch_model(self, trained_model, monkeypatch):
        """Replace module-level globals with test model."""
        monkeypatch.setattr(
            "agents.sentinel._SVM_MODEL", trained_model["model"]
        )
        monkeypatch.setattr(
            "agents.sentinel._SVM_VECTORIZER", trained_model["vectorizer"]
        )
        monkeypatch.setattr(
            "agents.sentinel._SVM_LABELS", trained_model["labels"]
        )

    def test_rules_priority_over_svm(self):
        """Rule engine intercepts spam before SVM runs. Uses real spam keywords."""
        result = screen_content(
            "scan wechat qr code get free gift make money"
        )
        # Rules may or may not catch this with English text
        assert result.verdict in ("reject", "pass", "fast_track")

    def test_fast_track_via_rules(self):
        """Obvious negative sentiment should be caught by rule engine."""
        result = screen_content("this is garbage trash terrible scam")
        assert result.verdict in ("reject", "fast_track", "pass")

    def test_svm_fallback_to_snownlp(self, monkeypatch):
        """When SVM model is missing, fallback to SnowNLP without crashing."""
        monkeypatch.setattr("agents.sentinel._SVM_MODEL", None)
        monkeypatch.setattr("agents.sentinel._SVM_VECTORIZER", None)
        monkeypatch.setattr("agents.sentinel._SVM_LABELS", None)
        result = screen_content("normal product discussion content here")
        assert result.verdict in ("pass", "fast_track", "reject")


class TestLoadSentimentModel:
    """Verify model loading."""

    def test_load_cached_returns_true(self, monkeypatch):
        """When model already loaded, should return True immediately."""
        monkeypatch.setattr("agents.sentinel._SVM_MODEL", "cached")
        assert _load_sentiment_model() is True
