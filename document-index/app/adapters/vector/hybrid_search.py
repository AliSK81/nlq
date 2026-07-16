from __future__ import annotations

from app.config import settings


def hybrid_search_enabled() -> bool:
    import os
    return os.environ.get("HYBRID_SEARCH", "0") == "1"


def get_search_params() -> dict:
    """Return Qdrant search params when hybrid mode is active."""
    if not hybrid_search_enabled():
        return {}
    return {
        "using": "dense",
        "search_params": {"hnsw_ef": 128},
    }
