from __future__ import annotations

from dataclasses import dataclass

from app.domain.document import IngestionStatus
from app.usecases.ports import DocumentRepo, DocumentSummary


@dataclass
class ListDocumentsRequest:
    tenant_id: str = "default"
    status: str | None = "INDEXED"
    limit: int = 50


@dataclass
class ListDocumentsResponse:
    documents: list[DocumentSummary]
    total: int


class ListDocuments:
    def __init__(self, repo: DocumentRepo) -> None:
        self._repo = repo

    def execute(self, request: ListDocumentsRequest) -> ListDocumentsResponse:
        status = IngestionStatus(request.status) if request.status else None
        docs = self._repo.list_documents(request.tenant_id, status, request.limit)
        summaries = [
            DocumentSummary(
                document_id=str(d.id),
                name=d.name,
                mime_type=d.mime_type,
                status=d.status.value,
                page_count=d.page_count,
                chunk_count=self._repo.count_chunks(d.id),
            )
            for d in docs
        ]
        return ListDocumentsResponse(documents=summaries, total=len(summaries))
