from __future__ import annotations

from app.usecases.ports import SearchHit


class RerankerPort:
    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        raise NotImplementedError


class PassthroughReranker:
    """Default no-op reranker — returns hits unchanged."""

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        return hits[:top_k]
