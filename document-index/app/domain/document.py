from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import NewType

DocumentId = NewType("DocumentId", uuid.UUID)


class IngestionStatus(str, Enum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


_VALID_TRANSITIONS: dict[IngestionStatus, set[IngestionStatus]] = {
    IngestionStatus.UPLOADED: {IngestionStatus.EXTRACTING, IngestionStatus.FAILED},
    IngestionStatus.EXTRACTING: {IngestionStatus.CHUNKING, IngestionStatus.FAILED},
    IngestionStatus.CHUNKING: {IngestionStatus.EMBEDDING, IngestionStatus.FAILED},
    IngestionStatus.EMBEDDING: {IngestionStatus.INDEXED, IngestionStatus.FAILED},
    IngestionStatus.INDEXED: set(),
    IngestionStatus.FAILED: set(),
}


def can_transition(from_status: IngestionStatus, to_status: IngestionStatus) -> bool:
    return to_status in _VALID_TRANSITIONS.get(from_status, set())


@dataclass
class Document:
    id: DocumentId
    tenant_id: str
    name: str
    mime_type: str
    content_hash: str
    size_bytes: int
    status: IngestionStatus = IngestionStatus.UPLOADED
    error: str | None = None
    extractor: str | None = None
    page_count: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    indexed_at: datetime | None = None

    def transition_to(self, new_status: IngestionStatus) -> None:
        if not can_transition(self.status, new_status):
            raise ValueError(f"Invalid transition {self.status.value} -> {new_status.value}")
        self.status = new_status
        if new_status == IngestionStatus.INDEXED:
            self.indexed_at = datetime.now(timezone.utc)

    @staticmethod
    def new_id() -> DocumentId:
        return DocumentId(uuid.uuid4())
