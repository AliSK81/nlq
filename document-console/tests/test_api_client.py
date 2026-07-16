import httpx
import pytest
import respx

from app.api_client import DocumentIndexClient, DocumentIndexError


@pytest.fixture
def api_base():
    return "http://document-index:8080"


@pytest.fixture
def client(api_base):
    return DocumentIndexClient(api_base, timeout=5)


@respx.mock
def test_health_ok(client, api_base):
    respx.get(f"{api_base}/health").mock(return_value=httpx.Response(200, json={"status": "ok"}))
    assert client.health() is True


@respx.mock
def test_ingest(client, api_base):
    route = respx.post(f"{api_base}/ingest").mock(
        return_value=httpx.Response(202, json={"document_id": "abc-123", "status": "UPLOADED"})
    )
    result = client.ingest("test.pdf", b"%PDF", "application/pdf")
    assert result.document_id == "abc-123"
    assert route.called


@respx.mock
def test_search(client, api_base):
    respx.post(f"{api_base}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "chunk_id": "c1",
                        "document_id": "d1",
                        "document_name": "doc.pdf",
                        "page": 1,
                        "section_path": None,
                        "score": 0.9,
                        "text": "hello",
                    }
                ],
                "total": 1,
            },
        )
    )
    result = client.search("hello")
    assert result.total == 1
    assert result.hits[0].chunk_id == "c1"


@respx.mock
def test_error_mapping(client, api_base):
    respx.get(f"{api_base}/documents/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Document not found"})
    )
    with pytest.raises(DocumentIndexError) as exc:
        client.get_document("missing")
    assert exc.value.status_code == 404
