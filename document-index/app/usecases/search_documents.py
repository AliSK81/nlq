from __future__ import annotations

from dataclasses import dataclass

from app.usecases.ports import DocumentRepo, Embedder, SearchHit, VectorIndex


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
    ) -> None:
        self._embedder = embedder
        self._vector_index = vector_index

    def execute(self, request: SearchDocumentsRequest) -> SearchDocumentsResponse:
        vector = self._embedder.embed_query(request.query)
        result = self._vector_index.search(
            query_vector=vector,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
            min_score=request.min_score,
            document_ids=request.document_ids,
        )
        return SearchDocumentsResponse(hits=result.hits, total=result.total)
