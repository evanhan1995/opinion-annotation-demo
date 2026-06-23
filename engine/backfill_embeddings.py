# -*- coding: utf-8 -*-
"""Backfill embeddings for all existing case files.

Usage:
    python engine/backfill_embeddings.py
    python engine/backfill_embeddings.py --force  # rebuild even if cached
"""
import io
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

if __name__ == "__main__":
    from engine.embeddings import EmbeddingService

    force = "--force" in sys.argv
    svc = EmbeddingService()

    if force:
        svc._cache = {}
        svc._save_cache()
        print("Cleared existing cache.")

    print(f"Starting backfill...")
    print(f"  Cases dir : wiki/cases/")
    print(f"  Force     : {force}")

    count = svc.batch_rebuild_all_embeddings()

    if count < 0:
        print("ERROR: Model not available. Install sentence-transformers first.")
        print("  pip install sentence-transformers>=3.0.0")
        sys.exit(1)
    elif count == 0:
        print("No case files found in wiki/cases/.")
    else:
        dim = len(next(iter(svc._cache.values()))) if svc._cache else 0
        print(f"Done. {count} embeddings generated ({dim}-dim).")
        print(f"Cache  : wiki/embeddings/case_embeddings.json")
