"""Lightweight OpenAPI smoke — Schemathesis optional deeper fuzz in CI later."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.delivery.rest import create_rest_router
from app.usecases.fetch_chunk import FetchChunk
from app.usecases.ingest_document import IngestDocument
from app.usecases.list_documents import ListDocuments
from app.usecases.search_documents import SearchDocuments
from tests.fakes import FakeEmbedder, FakeRepo, FakeVectorIndex


def test_openapi_exposes_search_and_ingest(tmp_path):
    repo = FakeRepo()
    index = FakeVectorIndex()
    embedder = FakeEmbedder()
    ingest = IngestDocument(repo, str(tmp_path), max_upload_mb=10)
    search = SearchDocuments(embedder, index)
    list_docs = ListDocuments(repo)
    fetch = FetchChunk(repo)
    app = FastAPI()
    app.include_router(create_rest_router(ingest, list_docs, fetch, search, repo, index))
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert "/search" in paths
    assert "/ingest" in paths
    assert "/documents" in paths
