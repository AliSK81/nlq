from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.domain.chunk import Chunk
from app.domain.document import DocumentId
from app.usecases.ports import SearchHit, SearchResult, SparseEmbedding

DENSE_NAME = "dense"
SPARSE_NAME = "sparse"


class QdrantIndex:
    def __init__(
        self,
        url: str,
        collection: str,
        dimension: int,
        hybrid: bool = True,
    ) -> None:
        self._client = QdrantClient(url=url)
        self._collection = collection
        self._dimension = dimension
        self._hybrid = hybrid

    def ensure_collection(self) -> None:
        collections = [c.name for c in self._client.get_collections().collections]
        if self._collection in collections:
            return

        vectors_config: dict | VectorParams = {
            DENSE_NAME: VectorParams(size=self._dimension, distance=Distance.COSINE),
        }
        sparse_config = {SPARSE_NAME: SparseVectorParams()} if self._hybrid else None
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_config,
        )
        for field in ("tenant_id", "document_id"):
            self._client.create_payload_index(
                collection_name=self._collection,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]],
        document_name: str,
        sparse_vectors: list[SparseEmbedding] | None = None,
    ) -> None:
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            if self._hybrid and sparse_vectors is not None:
                sparse = sparse_vectors[i]
                point_vector: dict = {
                    DENSE_NAME: vector,
                    SPARSE_NAME: SparseVector(indices=sparse.indices, values=sparse.values),
                }
            else:
                point_vector = {DENSE_NAME: vector}
            points.append(
                PointStruct(
                    id=str(chunk.id),
                    vector=point_vector,
                    payload={
                        "tenant_id": chunk.tenant_id,
                        "document_id": str(chunk.document_id),
                        "document_name": document_name,
                        "ordinal": chunk.ordinal,
                        "page": chunk.page,
                        "section_path": chunk.section_path,
                        "text": chunk.text,
                    },
                )
            )
        self._client.upsert(collection_name=self._collection, points=points)

    def _filter(
        self,
        tenant_id: str,
        document_ids: list[str] | None,
    ) -> Filter:
        must: list[FieldCondition] = [
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
        ]
        if document_ids:
            must.append(
                FieldCondition(key="document_id", match=MatchAny(any=document_ids))
            )
        return Filter(must=must)

    def search(
        self,
        query_vector: list[float],
        tenant_id: str,
        top_k: int,
        min_score: float,
        document_ids: list[str] | None = None,
        query_sparse: SparseEmbedding | None = None,
    ) -> SearchResult:
        query_filter = self._filter(tenant_id, document_ids)

        if self._hybrid and query_sparse is not None:
            sparse = SparseVector(indices=query_sparse.indices, values=query_sparse.values)
            response = self._client.query_points(
                collection_name=self._collection,
                prefetch=[
                    Prefetch(
                        query=query_vector,
                        using=DENSE_NAME,
                        filter=query_filter,
                        limit=max(top_k * 3, top_k),
                    ),
                    Prefetch(
                        query=sparse,
                        using=SPARSE_NAME,
                        filter=query_filter,
                        limit=max(top_k * 3, top_k),
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=top_k,
                score_threshold=None,
            )
        else:
            response = self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
                using=DENSE_NAME,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=min_score,
            )

        # RRF fusion scores are rank-based (not cosine); skip min_score for hybrid.
        apply_threshold = not (self._hybrid and query_sparse is not None)
        hits = []
        for r in response.points:
            score = float(r.score)
            if apply_threshold and score < min_score:
                continue
            hits.append(
                SearchHit(
                    chunk_id=str(r.id),
                    document_id=str(r.payload.get("document_id", "")),
                    document_name=str(r.payload.get("document_name", "")),
                    page=r.payload.get("page"),
                    section_path=r.payload.get("section_path"),
                    score=score,
                    text=str(r.payload.get("text", "")),
                )
            )
        return SearchResult(hits=hits[:top_k], total=len(hits[:top_k]))

    def delete_by_document(self, document_id: DocumentId) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(document_id)),
                    )
                ]
            ),
        )
