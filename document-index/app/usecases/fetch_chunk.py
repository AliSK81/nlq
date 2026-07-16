from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.chunk import ChunkId
from app.domain.errors import ChunkNotFoundError, DocumentNotFoundError
from app.usecases.ports import DocumentRepo


@dataclass
class FetchChunkRequest:
    chunk_id: str
    neighbors: int = 1


@dataclass
class FetchChunkResponse:
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    section_path: str | None
    text: str
    context_before: str | None
    context_after: str | None


class FetchChunk:
    def __init__(self, repo: DocumentRepo) -> None:
        self._repo = repo

    def execute(self, request: FetchChunkRequest) -> FetchChunkResponse:
        chunk, before, after = self._repo.get_chunk_neighbors(
            ChunkId(uuid.UUID(request.chunk_id)),
            request.neighbors,
        )
        if not chunk:
            raise ChunkNotFoundError(request.chunk_id)

        doc = self._repo.get(chunk.document_id)
        if not doc:
            raise DocumentNotFoundError(str(chunk.document_id))

        return FetchChunkResponse(
            chunk_id=str(chunk.id),
            document_id=str(chunk.document_id),
            document_name=doc.name,
            page=chunk.page,
            section_path=chunk.section_path,
            text=chunk.text,
            context_before=before.text if before else None,
            context_after=after.text if after else None,
        )
