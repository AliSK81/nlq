from __future__ import annotations

import uuid

from app.domain.chunk import Chunk, ChunkId
from app.domain.document import Document, DocumentId, IngestionStatus
from app.usecases.ports import (
    SearchHit,
    SearchResult,
)


class FakeRepo:
    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}
        self.chunks: dict[str, Chunk] = {}
        self.jobs: list[str] = []

    def save(self, document: Document) -> None:
        self.documents[str(document.id)] = document
        self.jobs.append(str(document.id))

    def get(self, document_id: DocumentId) -> Document | None:
        return self.documents.get(str(document_id))

    def get_by_hash(self, tenant_id: str, content_hash: str) -> Document | None:
        for d in self.documents.values():
            if d.tenant_id == tenant_id and d.content_hash == content_hash:
                return d
        return None

    def update(self, document: Document) -> None:
        self.documents[str(document.id)] = document

    def delete(self, document_id: DocumentId) -> None:
        self.documents.pop(str(document_id), None)

    def list_documents(
        self,
        tenant_id: str,
        status: IngestionStatus | None = None,
        limit: int = 50,
    ) -> list[Document]:
        docs = [d for d in self.documents.values() if d.tenant_id == tenant_id]
        if status:
            docs = [d for d in docs if d.status == status]
        return docs[:limit]

    def save_chunks(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            self.chunks[str(c.id)] = c

    def get_chunks(self, document_id: DocumentId) -> list[Chunk]:
        return sorted(
            [c for c in self.chunks.values() if c.document_id == document_id],
            key=lambda c: c.ordinal,
        )

    def get_chunk(self, chunk_id: ChunkId) -> Chunk | None:
        return self.chunks.get(str(chunk_id))

    def get_chunk_neighbors(
        self, chunk_id: ChunkId, neighbors: int
    ) -> tuple[Chunk | None, Chunk | None, Chunk | None]:
        chunk = self.get_chunk(chunk_id)
        if not chunk:
            return None, None, None
        all_c = self.get_chunks(chunk.document_id)
        idx = next((i for i, c in enumerate(all_c) if c.id == chunk_id), -1)
        before = all_c[idx - neighbors] if idx - neighbors >= 0 else None
        after = all_c[idx + neighbors] if idx + neighbors < len(all_c) else None
        return chunk, before, after

    def count_chunks(self, document_id: DocumentId) -> int:
        return len(self.get_chunks(document_id))

    def claim_pending_job(self) -> DocumentId | None:
        if not self.jobs:
            return None
        return DocumentId(uuid.UUID(self.jobs.pop(0)))

    def mark_job_failed(self, document_id: DocumentId, error: str) -> None:
        pass


class FakeEmbedder:
    dimension = 384
    hybrid_enabled = False

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self.dimension for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * self.dimension

    def embed_passages_sparse(self, texts: list[str]):
        return []

    def embed_query_sparse(self, text: str):
        return None


class FakeVectorIndex:
    def __init__(self) -> None:
        self.points: list[SearchHit] = []

    def ensure_collection(self) -> None:
        pass

    def upsert_chunks(self, chunks, vectors, document_name, sparse_vectors=None) -> None:
        for c in chunks:
            self.points.append(
                SearchHit(
                    chunk_id=str(c.id),
                    document_id=str(c.document_id),
                    document_name=document_name,
                    page=c.page,
                    section_path=c.section_path,
                    score=0.9,
                    text=c.text,
                )
            )

    def search(
        self,
        query_vector,
        tenant_id,
        top_k,
        min_score,
        document_ids=None,
        query_sparse=None,
    ) -> SearchResult:
        hits = self.points
        if document_ids:
            hits = [h for h in hits if h.document_id in document_ids]
        hits = hits[:top_k]
        return SearchResult(hits=hits, total=len(hits))

    def delete_by_document(self, document_id: DocumentId) -> None:
        self.points = [p for p in self.points if p.document_id != str(document_id)]
