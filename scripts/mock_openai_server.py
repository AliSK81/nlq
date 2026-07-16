#!/usr/bin/env python3
"""Minimal OpenAI-compatible chat completions server for CI / local stack tests."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _reply_for(messages: list[dict]) -> str:
    joined = "\n".join(str(m.get("content", "")) for m in messages).lower()
    if '"intent"' in joined or "one of: chitchat" in joined:
        return json.dumps({"intent": "file_query", "message_text": None})
    if "prepare queries" in joined or "standalone_question" in joined:
        return json.dumps(
            {
                "standalone_question": "What was revenue growth?",
                "search_query": "revenue growth",
                "document_scope": "all",
                "extra_search_queries": [],
                "requires_multi_document": False,
                "retrieval_mode": "semantic",
                "target_document_name": None,
            }
        )
    if "rephrase this search query" in joined:
        return "revenue growth Q3"
    return json.dumps(
        {
            "answer": "Revenue grew 20%.",
            "citations": [{"document_name": "smoke.txt"}],
            "confidence": 0.9,
        }
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter CI logs
        return

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/models") or self.path in ("/", "/health", "/v1/models"):
            self._json(
                200,
                {
                    "object": "list",
                    "data": [{"id": "mock", "object": "model", "owned_by": "nlq-ci"}],
                },
            )
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            body = {}
        content = _reply_for(body.get("messages") or [])
        self._json(
            200,
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 8, "completion_tokens": 16, "total_tokens": 24},
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"mock openai listening on {args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
