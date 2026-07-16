from __future__ import annotations

import json
from typing import Any

import httpx

from app.usecases.ports import RetrievalPort


class DocumentIndexClient:
    def __init__(self, base_url: str, api_version: str, timeout: int) -> None:
        self._url = f"{base_url.rstrip('/')}/tools"
        self._api_version = api_version
        self._timeout = timeout

    def _headers(self, auth: dict[str, str | None]) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "X-Api-Version": self._api_version,
        }
        for key in ("cookie", "authorization", "x_auth_token"):
            val = auth.get(key)
            if val:
                header_name = "Cookie" if key == "cookie" else key.replace("_", "-").title()
                if key == "authorization":
                    header_name = "Authorization"
                elif key == "x_auth_token":
                    header_name = "X-Auth-Token"
                headers[header_name] = val
        return headers

    def _parse_response(self, resp: httpx.Response) -> dict[str, Any]:
        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            for line in resp.text.splitlines():
                if line.startswith("data: "):
                    return json.loads(line[6:])
            raise RuntimeError("Empty SSE response from document index")
        return resp.json()

    def _call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        auth: dict[str, str | None],
    ) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        headers = self._headers(auth)
        headers["Accept"] = "application/json"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(self._url, json=payload, headers=headers)
            resp.raise_for_status()
            data = self._parse_response(resp)

        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))

        result = data.get("result", {})
        if result.get("isError"):
            content = result.get("content", [{}])
            raise RuntimeError(content[0].get("text", "Document index tool error"))

        for item in result.get("content", []):
            if item.get("type") == "text":
                return json.loads(item["text"])
        return {}

    def search(
        self,
        query: str,
        top_k: int,
        min_score: float,
        auth: dict[str, str | None],
    ) -> list[dict]:
        data = self._call_tool(
            "search_documents",
            {"query": query, "top_k": top_k, "min_score": min_score},
            auth,
        )
        return data.get("hits", [])

    def list_documents(self, auth: dict[str, str | None]) -> list[dict]:
        data = self._call_tool("list_documents", {"status": "INDEXED", "limit": 50}, auth)
        return data.get("documents", [])
