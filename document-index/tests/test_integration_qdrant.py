"""Optional integration tests against real Qdrant via testcontainers.

Skipped when Docker is unavailable.
"""

from __future__ import annotations

import pytest

pytest.importorskip("testcontainers")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def qdrant_url():
    try:
        from testcontainers.core.container import DockerContainer
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"testcontainers unavailable: {exc}")

    container = DockerContainer("qdrant/qdrant:v1.13.2").with_exposed_ports(6333)
    container.start()
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6333)
        yield f"http://{host}:{port}"
    finally:
        container.stop()


def test_qdrant_hybrid_collection_roundtrip(qdrant_url: str):
    from app.adapters.vector.qdrant_index import QdrantIndex
    from app.domain.chunk import Chunk
    from app.domain.document import DocumentId
    from app.usecases.ports import SparseEmbedding
    import uuid

    index = QdrantIndex(qdrant_url, "test_chunks", dimension=8, hybrid=True)
    index.ensure_collection()
    doc_id = DocumentId(uuid.uuid4())
    chunk = Chunk(
        id=Chunk.new_id(),
        document_id=doc_id,
        tenant_id="default",
        ordinal=0,
        text="Revenue grew 20%",
        page=1,
    )
    dense = [[0.1] * 8]
    sparse = [SparseEmbedding(indices=[1, 5], values=[0.9, 0.4])]
    index.upsert_chunks([chunk], dense, "report.pdf", sparse_vectors=sparse)
    result = index.search(
        query_vector=[0.1] * 8,
        tenant_id="default",
        top_k=5,
        min_score=0.0,
        query_sparse=SparseEmbedding(indices=[1], values=[1.0]),
    )
    assert result.total >= 1
    assert result.hits[0].document_name == "report.pdf"

    # multi-doc filter uses MatchAny (OR), not AND
    other = str(uuid.uuid4())
    result2 = index.search(
        query_vector=[0.1] * 8,
        tenant_id="default",
        top_k=5,
        min_score=0.0,
        document_ids=[str(doc_id), other],
        query_sparse=SparseEmbedding(indices=[1], values=[1.0]),
    )
    assert result2.total >= 1
