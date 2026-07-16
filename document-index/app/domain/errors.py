class DomainError(Exception):
    """Base domain error."""


class DocumentNotFoundError(DomainError):
    def __init__(self, document_id: str) -> None:
        super().__init__(f"Document not found: {document_id}")
        self.document_id = document_id


class ChunkNotFoundError(DomainError):
    def __init__(self, chunk_id: str) -> None:
        super().__init__(f"Chunk not found: {chunk_id}")
        self.chunk_id = chunk_id


class DuplicateDocumentError(DomainError):
    def __init__(self, content_hash: str) -> None:
        super().__init__(f"Document with hash already exists: {content_hash}")
        self.content_hash = content_hash


class InvalidStatusTransitionError(DomainError):
    pass
