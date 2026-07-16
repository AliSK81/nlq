from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import NewType

from app.domain.document import DocumentId

ChunkId = NewType("ChunkId", uuid.UUID)


@dataclass
class Citation:
    document_id: str
    document_name: str
    page: int | None
    section_path: str | None
    chunk_id: str | None = None


@dataclass
class Chunk:
    id: ChunkId
    document_id: DocumentId
    tenant_id: str
    ordinal: int
    text: str
    section_path: str | None = None
    page: int | None = None
    token_count: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def new_id() -> ChunkId:
        return ChunkId(uuid.uuid4())

    def to_citation(self, document_name: str) -> Citation:
        return Citation(
            document_id=str(self.document_id),
            document_name=document_name,
            page=self.page,
            section_path=self.section_path,
            chunk_id=str(self.id),
        )
