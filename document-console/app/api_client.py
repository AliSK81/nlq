from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class DocumentIndexError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class IngestResult:
    document_id: str
    status: str


@dataclass
class DocumentRow:
    document_id: str
    name: str
    mime_type: str
    status: str
    page_count: int | None
    chunk_count: int


@dataclass
class DocumentDetail:
    document_id: str
    name: str
    mime_type: str
    status: str
    error: str | None
    page_count: int | None
    chunk_count: int


@dataclass
class SearchHit:
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    section_path: str | None
    score: float
    text: str


@dataclass
class SearchResult:
    hits: list[SearchHit]
    total: int


@dataclass
class ChunkDetail:
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    section_path: str | None
    text: str
    context_before: str | None
    context_after: str | None


class DocumentIndexClient:
    def __init__(self, base_url: str, timeout: int = 120) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.request(method, f"{self._base}{path}", json=json, files=files, params=params)
        except httpx.RequestError as exc:
            raise DocumentIndexError(f"Cannot reach document-index: {exc}") from exc

        if resp.status_code >= 400:
            detail = resp.text.strip() or resp.reason_phrase
            try:
                body = resp.json()
                if isinstance(body, dict) and body.get("detail"):
                    detail = str(body["detail"])
            except Exception:
                pass
            raise DocumentIndexError(detail, resp.status_code)
        return resp

    def health(self) -> bool:
        try:
            resp = self._request("GET", "/health")
            return resp.json().get("status") == "ok"
        except DocumentIndexError:
            return False

    def ingest(self, filename: str, content: bytes, mime_type: str = "application/octet-stream") -> IngestResult:
        resp = self._request(
            "POST",
            "/ingest",
            files={"file": (filename, content, mime_type)},
        )
        data = resp.json()
        return IngestResult(document_id=data["document_id"], status=data["status"])

    def list_documents(self, status: str | None = None, limit: int = 50) -> list[DocumentRow]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        resp = self._request("GET", "/documents", params=params)
        return [
            DocumentRow(
                document_id=d["document_id"],
                name=d["name"],
                mime_type=d["mime_type"],
                status=d["status"],
                page_count=d.get("page_count"),
                chunk_count=d.get("chunk_count", 0),
            )
            for d in resp.json()
        ]

    def get_document(self, document_id: str) -> DocumentDetail:
        resp = self._request("GET", f"/documents/{document_id}")
        d = resp.json()
        return DocumentDetail(
            document_id=d["document_id"],
            name=d["name"],
            mime_type=d["mime_type"],
            status=d["status"],
            error=d.get("error"),
            page_count=d.get("page_count"),
            chunk_count=d.get("chunk_count", 0),
        )

    def delete_document(self, document_id: str) -> None:
        self._request("DELETE", f"/documents/{document_id}")

    def search(
        self,
        query: str,
        top_k: int = 8,
        min_score: float = 0.3,
        document_ids: list[str] | None = None,
    ) -> SearchResult:
        body: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "min_score": min_score,
        }
        if document_ids:
            body["document_ids"] = document_ids
        resp = self._request("POST", "/search", json=body)
        data = resp.json()
        hits = [
            SearchHit(
                chunk_id=h["chunk_id"],
                document_id=h["document_id"],
                document_name=h["document_name"],
                page=h.get("page"),
                section_path=h.get("section_path"),
                score=h["score"],
                text=h["text"],
            )
            for h in data.get("hits", [])
        ]
        return SearchResult(hits=hits, total=data.get("total", len(hits)))

    def get_chunk(self, chunk_id: str, neighbors: int = 1) -> ChunkDetail:
        resp = self._request("GET", f"/chunks/{chunk_id}", params={"neighbors": neighbors})
        d = resp.json()
        return ChunkDetail(
            chunk_id=d["chunk_id"],
            document_id=d["document_id"],
            document_name=d["document_name"],
            page=d.get("page"),
            section_path=d.get("section_path"),
            text=d["text"],
            context_before=d.get("context_before"),
            context_after=d.get("context_after"),
        )
