from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.delivery.openai_compat import create_openai_router


@pytest.fixture
def client():
    factory = MagicMock()
    factory.run.return_value = {
        "answer_text": "The revenue grew 20% [report.pdf p.4]",
        "intent": "file_query",
        "hits": [{"document_name": "report.pdf"}],
        "grounded": True,
        "total_tokens_used": 60,
        "steps": [{"node": "classify", "duration_ms": 10}],
    }
    app = FastAPI()
    app.include_router(create_openai_router(factory))
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_models(client):
    resp = client.get("/v1/models")
    ids = {m["id"] for m in resp.json()["data"]}
    assert "file-qa-agent" in ids


def test_chat_completions(client):
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "file-qa-agent",
            "messages": [{"role": "user", "content": "What is the revenue?"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "revenue" in data["choices"][0]["message"]["content"].lower()
    assert "reasoning_content" in data["choices"][0]["message"]
