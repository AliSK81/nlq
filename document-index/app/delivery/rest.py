from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.domain.document import DocumentId, IngestionStatus
from app.domain.errors import ChunkNotFoundError, DocumentNotFoundError, DuplicateDocumentError
from app.usecases.fetch_chunk import FetchChunk, FetchChunkRequest
from app.usecases.ingest_document import IngestDocument
from app.usecases.list_documents import ListDocuments, ListDocumentsRequest
from app.usecases.ports import DocumentRepo, VectorIndex
from app.usecases.search_documents import SearchDocuments, SearchDocumentsRequest


class IngestResponse(BaseModel):
    document_id: str
    status: str


class DocumentDetail(BaseModel):
    document_id: str
    name: str
    mime_type: str
    status: str
    error: str | None
    page_count: int | None
    chunk_count: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    min_score: float = 0.3
    document_ids: list[str] | None = None
    tenant_id: str = "default"


class SearchHitResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    section_path: str | None
    score: float
    text: str


class SearchResponse(BaseModel):
    hits: list[SearchHitResponse]
    total: int


class ChunkDetail(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    section_path: str | None
    text: str
    context_before: str | None
    context_after: str | None


class DocumentChunkRow(BaseModel):
    chunk_id: str
    ordinal: int
    page: int | None
    section_path: str | None
    text: str


class DocumentChunksResponse(BaseModel):
    document_id: str
    document_name: str
    chunks: list[DocumentChunkRow]
    total: int


def create_rest_router(
    ingest: IngestDocument,
    list_docs: ListDocuments,
    fetch_chunk: FetchChunk,
    search: SearchDocuments,
    repo: DocumentRepo,
    vector_index: VectorIndex,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/ingest", status_code=202)
    async def ingest_file(
        file: UploadFile = File(...),
        tenant_id: str = "default",
    ) -> IngestResponse:
        blob = await file.read()
        mime = file.content_type or "application/octet-stream"
        try:
            result = ingest.execute(file.filename or "upload", mime, blob, tenant_id)
        except DuplicateDocumentError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return IngestResponse(document_id=result.document_id, status=result.status)

    @router.get("/documents")
    def get_documents(status: str | None = None, limit: int = 50) -> list[dict]:
        resp = list_docs.execute(ListDocumentsRequest(status=status, limit=limit))
        return [
            {
                "document_id": d.document_id,
                "name": d.name,
                "mime_type": d.mime_type,
                "status": d.status,
                "page_count": d.page_count,
                "chunk_count": d.chunk_count,
            }
            for d in resp.documents
        ]

    @router.get("/documents/{document_id}")
    def get_document(document_id: str) -> DocumentDetail:
        doc = repo.get(DocumentId(uuid.UUID(document_id)))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentDetail(
            document_id=str(doc.id),
            name=doc.name,
            mime_type=doc.mime_type,
            status=doc.status.value,
            error=doc.error,
            page_count=doc.page_count,
            chunk_count=repo.count_chunks(doc.id),
        )

    @router.delete("/documents/{document_id}", status_code=204)
    def delete_document(document_id: str) -> None:
        doc_id = DocumentId(uuid.UUID(document_id))
        doc = repo.get(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        vector_index.delete_by_document(doc_id)
        repo.delete(doc_id)

    @router.post("/search")
    def search_documents(body: SearchRequest) -> SearchResponse:
        resp = search.execute(
            SearchDocumentsRequest(
                query=body.query,
                tenant_id=body.tenant_id,
                top_k=body.top_k,
                min_score=body.min_score,
                document_ids=body.document_ids,
            )
        )
        return SearchResponse(
            hits=[
                SearchHitResponse(
                    chunk_id=h.chunk_id,
                    document_id=h.document_id,
                    document_name=h.document_name,
                    page=h.page,
                    section_path=h.section_path,
                    score=h.score,
                    text=h.text,
                )
                for h in resp.hits
            ],
            total=resp.total,
        )

    @router.get("/documents/{document_id}/chunks")
    def list_document_chunks(document_id: str) -> DocumentChunksResponse:
        doc = repo.get(DocumentId(uuid.UUID(document_id)))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        rows = repo.get_chunks(doc.id)
        return DocumentChunksResponse(
            document_id=str(doc.id),
            document_name=doc.name,
            chunks=[
                DocumentChunkRow(
                    chunk_id=str(c.id),
                    ordinal=c.ordinal,
                    page=c.page,
                    section_path=c.section_path,
                    text=c.text,
                )
                for c in rows
            ],
            total=len(rows),
        )

    @router.get("/chunks/{chunk_id}")
    def get_chunk(chunk_id: str, neighbors: int = 1) -> ChunkDetail:
        try:
            resp = fetch_chunk.execute(FetchChunkRequest(chunk_id=chunk_id, neighbors=neighbors))
        except ChunkNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return ChunkDetail(
            chunk_id=resp.chunk_id,
            document_id=resp.document_id,
            document_name=resp.document_name,
            page=resp.page,
            section_path=resp.section_path,
            text=resp.text,
            context_before=resp.context_before,
            context_after=resp.context_after,
        )

    return router
