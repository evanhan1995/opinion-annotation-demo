# -*- coding: utf-8 -*-
"""
舆情指挥系统 — 本地 Embedding 语义搜索服务

Model: BAAI/bge-small-zh-v1.5 (384-dim, ~33MB, CPU inference)
Storage: wiki/embeddings/case_embeddings.json
"""
import io
import json
import sys
from pathlib import Path
from typing import Optional

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = PROJECT_ROOT / "wiki"
EMBEDDINGS_DIR = WIKI_DIR / "embeddings"
EMBEDDINGS_FILE = EMBEDDINGS_DIR / "case_embeddings.json"


def _bigram_tokenize(text: str) -> set:
    """Extract bigram character tokens from text."""
    cleaned = text.lower()
    return {cleaned[i:i+2] for i in range(len(cleaned)-1)}


class EmbeddingService:
    """Singleton service for semantic search with local embeddings.

    Usage:
        svc = EmbeddingService()
        results = svc.hybrid_search("食品安全", top_k=10)
        similar = svc.find_similar_cases("wiki/cases/douyin/case-001.md", top_k=5)
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._model = None
        self._model_attempted = False
        self._cache: dict = {}
        self._load_cache()

    # ── model lifecycle ─────────────────────────────────────────────────

    def _ensure_model(self) -> bool:
        if self._model_attempted:
            return self._model is not None
        self._model_attempted = True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        except Exception:
            pass
        return self._model is not None

    # ── cache persistence ───────────────────────────────────────────────

    def _load_cache(self):
        if EMBEDDINGS_FILE.exists():
            try:
                with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}
        else:
            self._cache = {}

    def _save_cache(self):
        EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(EMBEDDINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    # ── core operations ─────────────────────────────────────────────────

    def compute_embedding(self, text: str) -> Optional[list]:
        """Compute 384-dim normalized embedding for text. Returns None if model unavailable."""
        if not text or not self._ensure_model():
            return None
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def get_or_create_embedding(self, case_path) -> Optional[list]:
        """Get cached embedding or compute from case file content."""
        path_str = str(case_path)
        if path_str in self._cache:
            return self._cache[path_str]
        try:
            text = Path(case_path).read_text(encoding="utf-8")
        except Exception:
            return None
        emb = self.compute_embedding(text)
        if emb is not None:
            self._cache[path_str] = emb
            self._save_cache()
        return emb

    @staticmethod
    def cosine_similarity(a: list, b: list) -> float:
        """Cosine similarity for two already-normalized vectors (dot product)."""
        return sum(x * y for x, y in zip(a, b))

    def remove_embedding(self, case_path: str):
        """Remove cached embedding for a deleted/renamed case."""
        if case_path in self._cache:
            del self._cache[case_path]
            self._save_cache()

    # ── search methods ──────────────────────────────────────────────────

    def _bigram_score(self, query: str, text: str) -> float:
        """Bigram overlap ratio — how much of the query's character bigrams
        appear in the target text."""
        q_bg = _bigram_tokenize(query)
        if not q_bg:
            return 0.0
        t_bg = _bigram_tokenize(text)
        return len(q_bg & t_bg) / len(q_bg)

    def semantic_search(self, query: str, top_k: int = 10) -> list:
        """Pure embedding similarity search. Returns [{path, score}, ...]."""
        query_emb = self.compute_embedding(query)
        if query_emb is None:
            return []
        results = []
        for path_str, emb in self._cache.items():
            score = self.cosine_similarity(query_emb, emb)
            results.append({"path": path_str, "score": round(score, 4)})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def hybrid_search(self, query: str, top_k: int = 10,
                      alpha: float = 0.7) -> list:
        """Hybrid search blending embedding similarity with keyword bigram overlap.

        alpha=0.7 weights embedding more heavily; keyword acts as a recall safety net
        for out-of-vocabulary terms.
        Returns [{path, score, semantic, keyword, title, ...}, ...].
        """
        model_ok = self._model is not None or self._ensure_model()
        semantic_results = self.semantic_search(query, top_k * 3) if model_ok else []
        semantic_map = {r["path"]: r["score"] for r in semantic_results}

        results = []
        seen = set()

        # Score every cached case with the hybrid formula
        for path_str in self._cache:
            try:
                text = Path(path_str).read_text(encoding="utf-8")
            except Exception:
                continue
            kw_score = self._bigram_score(query, text)
            sem_score = semantic_map.get(path_str, 0.0)
            hybrid = alpha * sem_score + (1 - alpha) * kw_score
            if hybrid > 0:
                results.append({
                    "path": path_str,
                    "score": round(hybrid, 4),
                    "semantic": round(sem_score, 4),
                    "keyword": round(kw_score, 4),
                })
                seen.add(path_str)

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def find_similar_cases(self, case_path, top_k: int = 5) -> list:
        """Find cases semantically similar to the given case, excluding itself."""
        path_str = str(case_path)
        emb = self.get_or_create_embedding(path_str)
        if emb is None:
            return []
        results = []
        for other_path, other_emb in self._cache.items():
            if other_path == path_str:
                continue
            score = self.cosine_similarity(emb, other_emb)
            results.append({"path": other_path, "score": round(score, 4)})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ── batch operations ────────────────────────────────────────────────

    def batch_rebuild_all_embeddings(self) -> int:
        """Scan wiki/cases/**/*.md and rebuild all embeddings. Returns count, or -1 if model unavailable."""
        if not self._ensure_model():
            return -1
        cases_dir = WIKI_DIR / "cases"
        if not cases_dir.exists():
            return 0
        new_cache = {}
        for md_path in sorted(cases_dir.rglob("*.md")):
            try:
                text = md_path.read_text(encoding="utf-8")
                emb = self.compute_embedding(text)
                if emb is not None:
                    new_cache[str(md_path)] = emb
            except Exception:
                pass
        self._cache = new_cache
        self._save_cache()
        return len(self._cache)

    # ── properties ──────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return self._model is not None

    @property
    def case_count(self) -> int:
        return len(self._cache)
