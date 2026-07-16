import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.delivery.rest import create_rest_router
from app.delivery.tool_rpc import create_tool_router
from app.usecases.fetch_chunk import FetchChunk
from app.usecases.ingest_document import IngestDocument
from app.usecases.list_documents import ListDocuments
from app.usecases.search_documents import SearchDocuments
from tests.fakes import FakeEmbedder, FakeRepo, FakeVectorIndex


@pytest.fixture
def client():
    repo = FakeRepo()
    embedder = FakeEmbedder()
    index = FakeVectorIndex()
    ingest = IngestDocument(repo, "/tmp", 50)
    search = SearchDocuments(embedder, index)
    list_docs = ListDocuments(repo)
    fetch_chunk = FetchChunk(repo)

    app = FastAPI()
    app.include_router(create_rest_router(ingest, list_docs, fetch_chunk, repo, index))
    app.include_router(create_tool_router(search, list_docs, fetch_chunk))
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_tools_list(client):
    resp = client.post(
        "/tools",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Accept": "application/json", "X-Api-Version": "1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    tools = data["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == {"search_documents", "list_documents", "fetch_chunk"}


def test_search_documents_contract(client):
    resp = client.post(
        "/tools",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_documents",
                "arguments": {"query": "test", "top_k": 8},
            },
        },
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert "content" in result
    assert result["content"][0]["type"] == "text"
    payload = json.loads(result["content"][0]["text"])
    assert "hits" in payload
    assert "total" in payload
