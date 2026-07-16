from __future__ import annotations

from dataclasses import dataclass

from app.usecases.ports import Embedder, Reranker, SearchHit, VectorIndex


@dataclass
class SearchDocumentsRequest:
    query: str
    tenant_id: str = "default"
    top_k: int = 8
    min_score: float = 0.3
    document_ids: list[str] | None = None


@dataclass
class SearchDocumentsResponse:
    hits: list[SearchHit]
    total: int


class SearchDocuments:
    def __init__(
        self,
        embedder: Embedder,
        vector_index: VectorIndex,
        reranker: Reranker | None = None,
        candidate_multiplier: int = 4,
    ) -> None:
        self._embedder = embedder
        self._vector_index = vector_index
        self._reranker = reranker
        self._candidate_multiplier = max(1, candidate_multiplier)

    def execute(self, request: SearchDocumentsRequest) -> SearchDocumentsResponse:
        dense = self._embedder.embed_query(request.query)
        sparse = (
            self._embedder.embed_query_sparse(request.query)
            if self._embedder.hybrid_enabled
            else None
        )
        candidate_k = (
            request.top_k * self._candidate_multiplier if self._reranker else request.top_k
        )
        result = self._vector_index.search(
            query_vector=dense,
            tenant_id=request.tenant_id,
            top_k=candidate_k,
            min_score=request.min_score,
            document_ids=request.document_ids,
            query_sparse=sparse,
        )
        hits = result.hits
        if self._reranker and hits:
            hits = self._reranker.rerank(request.query, hits, request.top_k)
        else:
            hits = hits[: request.top_k]
        return SearchDocumentsResponse(hits=hits, total=len(hits))
