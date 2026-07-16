from __future__ import annotations

from typing import Any

import httpx


class DocumentIndexClient:
    """REST client for document-index. Prefer /search and /documents over JSON-RPC /tools."""

    def __init__(self, base_url: str, api_version: str, timeout: int) -> None:
        self._base = base_url.rstrip("/")
        self._api_version = api_version
        self._timeout = timeout

    def _headers(self, auth: dict[str, str | None]) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Api-Version": self._api_version,
        }
        for key in ("cookie", "authorization", "x_auth_token"):
            val = auth.get(key)
            if val:
                if key == "cookie":
                    headers["Cookie"] = val
                elif key == "authorization":
                    headers["Authorization"] = val
                elif key == "x_auth_token":
                    headers["X-Auth-Token"] = val
        return headers

    def search(
        self,
        query: str,
        top_k: int,
        min_score: float,
        auth: dict[str, str | None],
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        body: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "min_score": min_score,
            "tenant_id": "default",
        }
        if document_ids:
            body["document_ids"] = document_ids
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base}/search",
                json=body,
                headers=self._headers(auth),
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("hits", [])

    def list_documents(self, auth: dict[str, str | None]) -> list[dict]:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base}/documents",
                params={"status": "INDEXED", "limit": 50},
                headers=self._headers(auth),
            )
            resp.raise_for_status()
            data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("documents", [])

    def list_document_chunks(self, document_id: str, auth: dict[str, str | None]) -> list[dict]:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base}/documents/{document_id}/chunks",
                headers=self._headers(auth),
            )
            resp.raise_for_status()
            data = resp.json()
        doc_name = data.get("document_name", "")
        return [
            {
                "chunk_id": c["chunk_id"],
                "document_id": data.get("document_id", document_id),
                "document_name": doc_name,
                "page": c.get("page"),
                "section_path": c.get("section_path"),
                "score": 1.0,
                "text": c.get("text", ""),
            }
            for c in data.get("chunks", [])
        ]
