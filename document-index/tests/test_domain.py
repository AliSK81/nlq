import uuid

import pytest

from app.domain.document import Document, DocumentId, IngestionStatus, can_transition


def test_valid_status_transitions():
    assert can_transition(IngestionStatus.UPLOADED, IngestionStatus.EXTRACTING)
    assert can_transition(IngestionStatus.EXTRACTING, IngestionStatus.CHUNKING)
    assert can_transition(IngestionStatus.CHUNKING, IngestionStatus.EMBEDDING)
    assert can_transition(IngestionStatus.EMBEDDING, IngestionStatus.INDEXED)
    assert not can_transition(IngestionStatus.INDEXED, IngestionStatus.UPLOADED)


def test_document_transition():
    doc = Document(
        id=DocumentId(uuid.uuid4()),
        tenant_id="default",
        name="test.pdf",
        mime_type="application/pdf",
        content_hash="abc",
        size_bytes=100,
    )
    doc.transition_to(IngestionStatus.EXTRACTING)
    assert doc.status == IngestionStatus.EXTRACTING
    with pytest.raises(ValueError):
        doc.transition_to(IngestionStatus.INDEXED)
