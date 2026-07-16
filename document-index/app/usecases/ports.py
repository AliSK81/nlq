from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.domain.chunk import Chunk, ChunkId
from app.domain.document import Document, DocumentId, IngestionStatus


@dataclass
class ExtractedBlock:
    text: str
    page: int | None = None
    section_path: str | None = None


@dataclass
class ExtractedDoc:
    markdown: str
    blocks: list[ExtractedBlock] = field(default_factory=list)
    page_count: int | None = None


@dataclass
class SearchHit:
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    section_path: str | None
    score: float
    text: str


@dataclass
class SearchResult:
    hits: list[SearchHit]
    total: int


@dataclass
class DocumentSummary:
    document_id: str
    name: str
    mime_type: str
    status: str
    page_count: int | None
    chunk_count: int


class Extractor(Protocol):
    name: str

    def supports(self, mime_type: str) -> bool: ...

    def extract(self, blob: bytes, filename: str, mime_type: str) -> ExtractedDoc: ...


class Chunker(Protocol):
    def chunk(self, doc: ExtractedDoc, document_id: DocumentId, tenant_id: str) -> list[Chunk]: ...


class Embedder(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class VectorIndex(Protocol):
    def ensure_collection(self) -> None: ...

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]],
        document_name: str,
    ) -> None: ...

    def search(
        self,
        query_vector: list[float],
        tenant_id: str,
        top_k: int,
        min_score: float,
        document_ids: list[str] | None = None,
    ) -> SearchResult: ...

    def delete_by_document(self, document_id: DocumentId) -> None: ...


class DocumentRepo(Protocol):
    def save(self, document: Document) -> None: ...

    def get(self, document_id: DocumentId) -> Document | None: ...

    def get_by_hash(self, tenant_id: str, content_hash: str) -> Document | None: ...

    def update(self, document: Document) -> None: ...

    def delete(self, document_id: DocumentId) -> None: ...

    def list_documents(
        self,
        tenant_id: str,
        status: IngestionStatus | None = None,
        limit: int = 50,
    ) -> list[Document]: ...

    def save_chunks(self, chunks: list[Chunk]) -> None: ...

    def get_chunks(self, document_id: DocumentId) -> list[Chunk]: ...

    def get_chunk(self, chunk_id: ChunkId) -> Chunk | None: ...

    def get_chunk_neighbors(
        self, chunk_id: ChunkId, neighbors: int
    ) -> tuple[Chunk | None, Chunk | None, Chunk | None]: ...

    def count_chunks(self, document_id: DocumentId) -> int: ...

    def claim_pending_job(self) -> DocumentId | None: ...

    def mark_job_failed(self, document_id: DocumentId, error: str) -> None: ...
