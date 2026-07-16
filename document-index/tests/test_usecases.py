import uuid

from app.domain.chunk import Chunk
from app.domain.document import Document, DocumentId, IngestionStatus
from app.usecases.fetch_chunk import FetchChunk, FetchChunkRequest
from app.usecases.ingest_document import IngestDocument
from app.usecases.list_documents import ListDocuments, ListDocumentsRequest
from app.usecases.search_documents import SearchDocuments, SearchDocumentsRequest
from tests.fakes import FakeEmbedder, FakeRepo, FakeVectorIndex


def test_ingest_document(tmp_path):
    repo = FakeRepo()
    ingest = IngestDocument(repo, str(tmp_path), max_upload_mb=10)
    result = ingest.execute("report.pdf", "application/pdf", b"pdf content")
    assert result.status == "UPLOADED"
    assert result.document_id in repo.documents


def test_search_documents():
    repo = FakeRepo()
    embedder = FakeEmbedder()
    index = FakeVectorIndex()
    doc_id = DocumentId(uuid.uuid4())
    chunk = Chunk(
        id=Chunk.new_id(),
        document_id=doc_id,
        tenant_id="default",
        ordinal=0,
        text="Revenue grew 20%",
        page=4,
    )
    index.upsert_chunks([chunk], embedder.embed_passages([chunk.text]), "report.pdf")

    search = SearchDocuments(embedder, index)
    resp = search.execute(SearchDocumentsRequest(query="revenue", top_k=5))
    assert resp.total == 1
    assert resp.hits[0].document_name == "report.pdf"
    assert resp.hits[0].page == 4


def test_list_documents():
    repo = FakeRepo()
    doc = Document(
        id=DocumentId(uuid.uuid4()),
        tenant_id="default",
        name="a.pdf",
        mime_type="application/pdf",
        content_hash="x",
        size_bytes=1,
        status=IngestionStatus.INDEXED,
    )
    repo.save(doc)
    resp = ListDocuments(repo).execute(ListDocumentsRequest())
    assert resp.total == 1
    assert resp.documents[0].name == "a.pdf"


def test_fetch_chunk():
    repo = FakeRepo()
    doc_id = DocumentId(uuid.uuid4())
    c1 = Chunk(id=Chunk.new_id(), document_id=doc_id, tenant_id="default", ordinal=0, text="first")
    c2 = Chunk(id=Chunk.new_id(), document_id=doc_id, tenant_id="default", ordinal=1, text="second")
    repo.save_chunks([c1, c2])
    repo.documents[str(doc_id)] = Document(
        id=doc_id,
        tenant_id="default",
        name="doc.pdf",
        mime_type="application/pdf",
        content_hash="h",
        size_bytes=1,
    )
    resp = FetchChunk(repo).execute(FetchChunkRequest(chunk_id=str(c2.id), neighbors=1))
    assert resp.text == "second"
    assert resp.context_before == "first"
