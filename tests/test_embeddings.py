# -*- coding: utf-8 -*-
"""Phase 2 embedding 模块测试 —— 语义搜索/混合搜索/持久化。

用法:
    python -m pytest tests/test_embeddings.py -v
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import engine.embeddings as emb_mod
from engine.embeddings import EmbeddingService, _bigram_tokenize


MOCK_DIM = 512  # BAAI/bge-small-zh-v1.5 dimension

def _normalize(v):
    import math
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v] if norm > 0 else v

# Normalized mock vectors so cosine_similarity(v, v) ≈ 1.0
_M1 = [0.01 * (i + 1) for i in range(MOCK_DIM)]
_M2 = [0.02 * (i + 1) for i in range(MOCK_DIM)]
_M3 = [-0.01 * (i + 1) for i in range(MOCK_DIM)]
MOCK_VEC_1 = _normalize(_M1)
MOCK_VEC_2 = _normalize(_M2)
MOCK_VEC_3 = _normalize(_M3)
MOCK_VEC_SMALL_1 = [0.1, 0.2, 0.3]
MOCK_VEC_SMALL_2 = [0.4, 0.5, 0.6]


def _make_mock_model():
    """Create a mock SentenceTransformer that returns controlled vectors."""
    model = MagicMock()
    def encode_side_effect(texts, normalize_embeddings=True):
        single_input = isinstance(texts, str)
        if single_input:
            texts = [texts]
        results = []
        for t in texts:
            if "食品" in t or "case-001" in t:
                results.append(MOCK_VEC_1)
            elif "安全" in t or "case-002" in t:
                results.append(MOCK_VEC_2)
            else:
                results.append(MOCK_VEC_3)
        import numpy as np
        arr = np.array(results)
        if single_input:
            arr = arr[0]
        return arr
    model.encode.side_effect = encode_side_effect
    return model


def _reset_singleton():
    EmbeddingService._instance = None


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton & lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

class TestSingleton:
    def test_same_instance(self):
        _reset_singleton()
        a = EmbeddingService()
        b = EmbeddingService()
        assert a is b

    def test_not_available_by_default(self):
        _reset_singleton()
        svc = EmbeddingService()
        assert svc.is_available is False
        # Model not loaded yet, but cache may have entries from backfill
        assert isinstance(svc.case_count, int)


# ═══════════════════════════════════════════════════════════════════════════════
# Bigram tokenize
# ═══════════════════════════════════════════════════════════════════════════════

class TestBigramTokenize:
    def test_chinese_bigrams(self):
        bg = _bigram_tokenize("食品安全")
        assert "食品" in bg
        assert "品安" in bg
        assert "安全" in bg

    def test_english_lowercase(self):
        bg = _bigram_tokenize("Hello")
        assert "he" in bg
        assert "el" in bg
        assert "lo" in bg

    def test_empty(self):
        assert _bigram_tokenize("") == set()
        assert _bigram_tokenize("a") == set()


# ═══════════════════════════════════════════════════════════════════════════════
# Cosine similarity
# ═══════════════════════════════════════════════════════════════════════════════

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [0.1, 0.2, 0.3]
        expected = 0.1*0.1 + 0.2*0.2 + 0.3*0.3
        assert EmbeddingService.cosine_similarity(v, v) == pytest.approx(expected)

    def test_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert EmbeddingService.cosine_similarity(a, b) == 0.0

    def test_opposite(self):
        a = [0.5, 0.5]
        b = [-0.5, -0.5]
        assert EmbeddingService.cosine_similarity(a, b) < 0


# ═══════════════════════════════════════════════════════════════════════════════
# Embedding computation (mocked model)
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeEmbedding:
    def test_returns_list(self):
        _reset_singleton()
        svc = EmbeddingService()
        svc._model = _make_mock_model()
        svc._model_attempted = True
        emb = svc.compute_embedding("测试食品安全")
        assert isinstance(emb, list)
        assert len(emb) == MOCK_DIM

    def test_returns_none_when_model_unavailable(self, monkeypatch):
        _reset_singleton()
        svc = EmbeddingService()
        monkeypatch.setattr(svc, "_ensure_model", lambda: False)
        assert svc.compute_embedding("test") is None

    def test_returns_none_for_empty_text(self):
        _reset_singleton()
        svc = EmbeddingService()
        svc._model = _make_mock_model()
        svc._model_attempted = True
        assert svc.compute_embedding("") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Cache & persistence
# ═══════════════════════════════════════════════════════════════════════════════

class TestCache:
    def test_remove_embedding(self):
        _reset_singleton()
        svc = EmbeddingService()
        svc._cache = {"a.md": MOCK_VEC_SMALL_1, "b.md": MOCK_VEC_SMALL_2}
        svc.remove_embedding("a.md")
        assert "a.md" not in svc._cache
        assert "b.md" in svc._cache

    def test_cache_persistence_roundtrip(self, monkeypatch, tmp_path):
        emb_file = tmp_path / "test_embeddings.json"
        monkeypatch.setattr(emb_mod, "EMBEDDINGS_FILE", emb_file)
        _reset_singleton()
        EmbeddingService._instance = None

        svc = EmbeddingService()
        svc._cache = {"test/path.md": MOCK_VEC_SMALL_1}
        svc._save_cache()
        assert emb_file.exists()

        _reset_singleton()
        svc2 = EmbeddingService()
        assert "test/path.md" in svc2._cache
        assert svc2._cache["test/path.md"] == MOCK_VEC_SMALL_1

    def test_load_empty_when_no_file(self, monkeypatch, tmp_path):
        _reset_singleton()
        emb_file = tmp_path / "nonexistent.json"
        monkeypatch.setattr(emb_mod, "EMBEDDINGS_FILE", emb_file)
        # Need to reset singleton after monkeypatching so init uses new path
        EmbeddingService._instance = None
        svc = EmbeddingService()
        assert svc._cache == {}


# ═══════════════════════════════════════════════════════════════════════════════
# Semantic search
# ═══════════════════════════════════════════════════════════════════════════════

class TestSemanticSearch:
    def test_returns_empty_when_model_unavailable(self, monkeypatch):
        _reset_singleton()
        svc = EmbeddingService()
        monkeypatch.setattr(svc, "_ensure_model", lambda: False)
        assert svc.semantic_search("test") == []

    def test_returns_ranked_results(self):
        _reset_singleton()
        svc = EmbeddingService()
        svc._model = _make_mock_model()
        svc._model_attempted = True
        svc._cache = {
            "a.md": MOCK_VEC_1,
            "b.md": MOCK_VEC_2,
            "c.md": MOCK_VEC_3,
        }
        results = svc.semantic_search("食品安全", top_k=3)
        assert len(results) == 3
        assert results[0]["path"] == "a.md"
        assert results[0]["score"] > results[2]["score"]

    def test_respects_top_k(self):
        _reset_singleton()
        svc = EmbeddingService()
        svc._model = _make_mock_model()
        svc._model_attempted = True
        svc._cache = {f"{i}.md": MOCK_VEC_1 for i in range(10)}
        results = svc.semantic_search("test", top_k=3)
        assert len(results) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Hybrid search
# ═══════════════════════════════════════════════════════════════════════════════

class TestHybridSearch:
    def test_empty_when_no_cache(self):
        _reset_singleton()
        svc = EmbeddingService()
        assert svc.hybrid_search("测试") == []


# ═══════════════════════════════════════════════════════════════════════════════
# find_similar_cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindSimilarCases:
    def test_excludes_self(self):
        _reset_singleton()
        svc = EmbeddingService()
        svc._cache = {
            "a.md": MOCK_VEC_1,
            "b.md": MOCK_VEC_2,
            "c.md": MOCK_VEC_3,
        }
        similar = svc.find_similar_cases("a.md", top_k=5)
        paths = [s["path"] for s in similar]
        assert "a.md" not in paths

    def test_returns_empty_when_only_self(self):
        _reset_singleton()
        svc = EmbeddingService()
        svc._cache = {"a.md": MOCK_VEC_1}
        similar = svc.find_similar_cases("a.md", top_k=3)
        assert similar == []

    def test_returns_ranked(self):
        _reset_singleton()
        svc = EmbeddingService()
        svc._cache = {
            "self.md": MOCK_VEC_1,
            "close.md": MOCK_VEC_1,
            "far.md": MOCK_VEC_3,
        }
        similar = svc.find_similar_cases("self.md", top_k=2)
        assert len(similar) == 2
        assert similar[0]["path"] == "close.md"
        assert similar[0]["score"] > similar[1]["score"]


# ═══════════════════════════════════════════════════════════════════════════════
# batch_rebuild_all_embeddings
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchRebuild:
    def test_returns_negative_when_model_unavailable(self, monkeypatch):
        _reset_singleton()
        svc = EmbeddingService()
        monkeypatch.setattr(svc, "_ensure_model", lambda: False)
        assert svc.batch_rebuild_all_embeddings() == -1

    def test_returns_zero_when_empty_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(emb_mod, "WIKI_DIR", tmp_path)
        _reset_singleton()
        EmbeddingService._instance = None
        (tmp_path / "cases").mkdir()
        svc = EmbeddingService()
        svc._model = _make_mock_model()
        svc._model_attempted = True
        count = svc.batch_rebuild_all_embeddings()
        assert count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: compute + cache + search round-trip
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoundTrip:
    def test_compute_and_search(self):
        _reset_singleton()
        svc = EmbeddingService()
        svc._model = _make_mock_model()
        svc._model_attempted = True

        emb1 = svc.compute_embedding("食品安全")
        svc._cache["doc1.md"] = emb1
        svc._cache["doc2.md"] = MOCK_VEC_2

        results = svc.semantic_search("食品相关", top_k=2)
        assert len(results) == 2
