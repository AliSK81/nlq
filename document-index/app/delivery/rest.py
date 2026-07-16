from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.domain.document import DocumentId, IngestionStatus
from app.domain.errors import DocumentNotFoundError, DuplicateDocumentError
from app.usecases.fetch_chunk import FetchChunk, FetchChunkRequest
from app.usecases.ingest_document import IngestDocument
from app.usecases.list_documents import ListDocuments, ListDocumentsRequest
from app.usecases.ports import DocumentRepo, VectorIndex


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


def create_rest_router(
    ingest: IngestDocument,
    list_docs: ListDocuments,
    fetch_chunk: FetchChunk,
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

    return router
