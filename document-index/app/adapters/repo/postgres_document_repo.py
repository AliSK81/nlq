from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
    update,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.domain.chunk import Chunk, ChunkId
from app.domain.document import Document, DocumentId, IngestionStatus
from app.domain.errors import DocumentNotFoundError
from app.usecases.ports import DocumentRepo


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False, default="UPLOADED")
    error = Column(Text)
    extractor = Column(String)
    page_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False)
    indexed_at = Column(DateTime(timezone=True))


class ChunkRow(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String, nullable=False, default="default")
    ordinal = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    section_path = Column(Text)
    page = Column(Integer)
    token_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False)


class IngestionJobRow(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    stage = Column(String, nullable=False, default="PENDING")
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text)
    updated_at = Column(DateTime(timezone=True), nullable=False)


def _row_to_document(row: DocumentRow) -> Document:
    return Document(
        id=DocumentId(uuid.UUID(row.id)),
        tenant_id=row.tenant_id,
        name=row.name,
        mime_type=row.mime_type,
        content_hash=row.content_hash,
        size_bytes=row.size_bytes,
        status=IngestionStatus(row.status),
        error=row.error,
        extractor=row.extractor,
        page_count=row.page_count,
        created_at=row.created_at,
        indexed_at=row.indexed_at,
    )


def _row_to_chunk(row: ChunkRow) -> Chunk:
    return Chunk(
        id=ChunkId(uuid.UUID(row.id)),
        document_id=DocumentId(uuid.UUID(row.document_id)),
        tenant_id=row.tenant_id,
        ordinal=row.ordinal,
        text=row.text,
        section_path=row.section_path,
        page=row.page,
        token_count=row.token_count,
        created_at=row.created_at,
    )


class PostgresDocumentRepo:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)

    def _session(self) -> Session:
        return self._session_factory()

    def save(self, document: Document) -> None:
        with self._session() as session:
            session.add(
                DocumentRow(
                    id=str(document.id),
                    tenant_id=document.tenant_id,
                    name=document.name,
                    mime_type=document.mime_type,
                    content_hash=document.content_hash,
                    size_bytes=document.size_bytes,
                    status=document.status.value,
                    error=document.error,
                    extractor=document.extractor,
                    page_count=document.page_count,
                    created_at=document.created_at,
                    indexed_at=document.indexed_at,
                )
            )
            session.add(
                IngestionJobRow(
                    id=str(uuid.uuid4()),
                    document_id=str(document.id),
                    stage="PENDING",
                    attempts=0,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

    def get(self, document_id: DocumentId) -> Document | None:
        with self._session() as session:
            row = session.get(DocumentRow, str(document_id))
            return _row_to_document(row) if row else None

    def get_by_hash(self, tenant_id: str, content_hash: str) -> Document | None:
        with self._session() as session:
            stmt = select(DocumentRow).where(
                DocumentRow.tenant_id == tenant_id,
                DocumentRow.content_hash == content_hash,
            )
            row = session.scalar(stmt)
            return _row_to_document(row) if row else None

    def update(self, document: Document) -> None:
        with self._session() as session:
            session.execute(
                update(DocumentRow)
                .where(DocumentRow.id == str(document.id))
                .values(
                    status=document.status.value,
                    error=document.error,
                    extractor=document.extractor,
                    page_count=document.page_count,
                    indexed_at=document.indexed_at,
                )
            )
            session.commit()

    def delete(self, document_id: DocumentId) -> None:
        with self._session() as session:
            row = session.get(DocumentRow, str(document_id))
            if row:
                session.delete(row)
                session.commit()

    def list_documents(
        self,
        tenant_id: str,
        status: IngestionStatus | None = None,
        limit: int = 50,
    ) -> list[Document]:
        with self._session() as session:
            stmt = select(DocumentRow).where(DocumentRow.tenant_id == tenant_id)
            if status:
                stmt = stmt.where(DocumentRow.status == status.value)
            stmt = stmt.limit(limit)
            return [_row_to_document(r) for r in session.scalars(stmt).all()]

    def save_chunks(self, chunks: list[Chunk]) -> None:
        with self._session() as session:
            for chunk in chunks:
                session.add(
                    ChunkRow(
                        id=str(chunk.id),
                        document_id=str(chunk.document_id),
                        tenant_id=chunk.tenant_id,
                        ordinal=chunk.ordinal,
                        text=chunk.text,
                        section_path=chunk.section_path,
                        page=chunk.page,
                        token_count=chunk.token_count,
                        created_at=chunk.created_at,
                    )
                )
            session.commit()

    def get_chunks(self, document_id: DocumentId) -> list[Chunk]:
        with self._session() as session:
            stmt = (
                select(ChunkRow)
                .where(ChunkRow.document_id == str(document_id))
                .order_by(ChunkRow.ordinal)
            )
            return [_row_to_chunk(r) for r in session.scalars(stmt).all()]

    def get_chunk(self, chunk_id: ChunkId) -> Chunk | None:
        with self._session() as session:
            row = session.get(ChunkRow, str(chunk_id))
            return _row_to_chunk(row) if row else None

    def get_chunk_neighbors(
        self, chunk_id: ChunkId, neighbors: int
    ) -> tuple[Chunk | None, Chunk | None, Chunk | None]:
        chunk = self.get_chunk(chunk_id)
        if not chunk:
            return None, None, None
        all_chunks = self.get_chunks(chunk.document_id)
        idx = next((i for i, c in enumerate(all_chunks) if c.id == chunk_id), -1)
        if idx < 0:
            return chunk, None, None
        before = all_chunks[idx - neighbors] if idx - neighbors >= 0 else None
        after = all_chunks[idx + neighbors] if idx + neighbors < len(all_chunks) else None
        return chunk, before, after

    def count_chunks(self, document_id: DocumentId) -> int:
        with self._session() as session:
            stmt = select(ChunkRow).where(ChunkRow.document_id == str(document_id))
            return len(session.scalars(stmt).all())

    def claim_pending_job(self) -> DocumentId | None:
        with self._session() as session:
            stmt = (
                select(IngestionJobRow)
                .where(IngestionJobRow.stage == "PENDING")
                .order_by(IngestionJobRow.updated_at)
                .limit(1)
            )
            job = session.scalar(stmt)
            if not job:
                return None
            job.stage = "PROCESSING"
            job.attempts += 1
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
            return DocumentId(uuid.UUID(job.document_id))

    def mark_job_failed(self, document_id: DocumentId, error: str) -> None:
        with self._session() as session:
            stmt = select(IngestionJobRow).where(
                IngestionJobRow.document_id == str(document_id)
            )
            job = session.scalar(stmt)
            if job:
                job.stage = "FAILED"
                job.last_error = error
                job.updated_at = datetime.now(timezone.utc)
                session.commit()
