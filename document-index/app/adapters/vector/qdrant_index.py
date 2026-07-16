from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.domain.chunk import Chunk
from app.domain.document import DocumentId
from app.usecases.ports import SearchHit, SearchResult, VectorIndex


class QdrantIndex:
    def __init__(
        self,
        url: str,
        collection: str,
        dimension: int,
    ) -> None:
        self._client = QdrantClient(url=url)
        self._collection = collection
        self._dimension = dimension

    def ensure_collection(self) -> None:
        collections = [c.name for c in self._client.get_collections().collections]
        if self._collection not in collections:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._dimension, distance=Distance.COSINE),
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
    ) -> None:
        points = [
            PointStruct(
                id=str(chunk.id),
                vector=vector,
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
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def search(
        self,
        query_vector: list[float],
        tenant_id: str,
        top_k: int,
        min_score: float,
        document_ids: list[str] | None = None,
    ) -> SearchResult:
        must = [FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
        if document_ids:
            for doc_id in document_ids:
                must.append(FieldCondition(key="document_id", match=MatchValue(value=doc_id)))

        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=Filter(must=must) if must else None,
            limit=top_k,
            score_threshold=min_score,
        )

        hits = [
            SearchHit(
                chunk_id=str(r.id),
                document_id=str(r.payload.get("document_id", "")),
                document_name=str(r.payload.get("document_name", "")),
                page=r.payload.get("page"),
                section_path=r.payload.get("section_path"),
                score=float(r.score),
                text=str(r.payload.get("text", "")),
            )
            for r in response.points
        ]
        return SearchResult(hits=hits, total=len(hits))

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
