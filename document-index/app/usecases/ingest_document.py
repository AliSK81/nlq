from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from app.domain.document import Document, DocumentId, IngestionStatus
from app.domain.errors import DuplicateDocumentError
from app.usecases.ports import DocumentRepo


@dataclass
class IngestResult:
    document_id: str
    status: str


class IngestDocument:
    def __init__(self, repo: DocumentRepo, upload_dir: str, max_upload_mb: int) -> None:
        self._repo = repo
        self._upload_dir = upload_dir
        self._max_bytes = max_upload_mb * 1024 * 1024

    def execute(
        self,
        filename: str,
        mime_type: str,
        blob: bytes,
        tenant_id: str = "default",
    ) -> IngestResult:
        if len(blob) > self._max_bytes:
            raise ValueError(f"File exceeds max size of {self._max_bytes} bytes")

        content_hash = hashlib.sha256(blob).hexdigest()
        existing = self._repo.get_by_hash(tenant_id, content_hash)
        if existing:
            raise DuplicateDocumentError(content_hash)

        doc_id = Document.new_id()
        Path(self._upload_dir).mkdir(parents=True, exist_ok=True)
        file_path = os.path.join(self._upload_dir, f"{doc_id}_{filename}")
        with open(file_path, "wb") as f:
            f.write(blob)

        document = Document(
            id=doc_id,
            tenant_id=tenant_id,
            name=filename,
            mime_type=mime_type,
            content_hash=content_hash,
            size_bytes=len(blob),
            status=IngestionStatus.UPLOADED,
        )
        self._repo.save(document)
        return IngestResult(document_id=str(doc_id), status=document.status.value)
