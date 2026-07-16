from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.domain.document import DocumentId
from app.domain.errors import ChunkNotFoundError, DocumentNotFoundError
from app.usecases.ports import DocumentRepo
from app.usecases.fetch_chunk import FetchChunk, FetchChunkRequest
from app.usecases.list_documents import ListDocuments, ListDocumentsRequest
from app.usecases.search_documents import SearchDocuments, SearchDocumentsRequest

TOOL_SCHEMAS = [
    {
        "name": "search_documents",
        "description": "Semantic search over indexed document chunks",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 8},
                "min_score": {"type": "number", "default": 0.3},
                "document_ids": {"type": "array", "items": {"type": "string"}},
                "tenant_id": {"type": "string", "default": "default"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_documents",
        "description": "List indexed documents",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "default": "INDEXED"},
                "limit": {"type": "integer", "default": 50},
                "tenant_id": {"type": "string", "default": "default"},
            },
        },
    },
    {
        "name": "list_document_chunks",
        "description": "List all indexed chunks for a document in ordinal order",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "fetch_chunk",
        "description": "Fetch a chunk with neighbor context",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chunk_id": {"type": "string"},
                "neighbors": {"type": "integer", "default": 1},
            },
            "required": ["chunk_id"],
        },
    },
]


def _tool_result(data: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(data)}],
        "isError": is_error,
    }


def create_tool_router(
    search: SearchDocuments,
    list_docs: ListDocuments,
    fetch_chunk: FetchChunk,
    repo: DocumentRepo,
) -> APIRouter:
    router = APIRouter()

    def _dispatch(params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name", "")
        args = params.get("arguments") or {}
        tenant_id = "default"

        if name == "search_documents":
            resp = search.execute(
                SearchDocumentsRequest(
                    query=args["query"],
                    tenant_id=tenant_id,
                    top_k=args.get("top_k", 8),
                    min_score=args.get("min_score", 0.3),
                    document_ids=args.get("document_ids"),
                )
            )
            return _tool_result(
                {
                    "hits": [
                        {
                            "chunk_id": h.chunk_id,
                            "document_id": h.document_id,
                            "document_name": h.document_name,
                            "page": h.page,
                            "section_path": h.section_path,
                            "score": h.score,
                            "text": h.text,
                        }
                        for h in resp.hits
                    ],
                    "total": resp.total,
                }
            )

        if name == "list_documents":
            resp = list_docs.execute(
                ListDocumentsRequest(
                    tenant_id=tenant_id,
                    status=args.get("status", "INDEXED"),
                    limit=args.get("limit", 50),
                )
            )
            return _tool_result(
                {
                    "documents": [
                        {
                            "document_id": d.document_id,
                            "name": d.name,
                            "mime_type": d.mime_type,
                            "status": d.status,
                            "page_count": d.page_count,
                            "chunk_count": d.chunk_count,
                        }
                        for d in resp.documents
                    ],
                    "total": resp.total,
                }
            )

        if name == "list_document_chunks":
            doc = repo.get(DocumentId(uuid.UUID(args["document_id"])))
            if not doc:
                return _tool_result({"error": "Document not found"}, is_error=True)
            rows = repo.get_chunks(doc.id)
            return _tool_result(
                {
                    "document_id": str(doc.id),
                    "document_name": doc.name,
                    "chunks": [
                        {
                            "chunk_id": str(c.id),
                            "ordinal": c.ordinal,
                            "page": c.page,
                            "section_path": c.section_path,
                            "text": c.text,
                        }
                        for c in rows
                    ],
                    "total": len(rows),
                }
            )

        if name == "fetch_chunk":
            resp = fetch_chunk.execute(
                FetchChunkRequest(
                    chunk_id=args["chunk_id"],
                    neighbors=args.get("neighbors", 1),
                )
            )
            return _tool_result(
                {
                    "chunk_id": resp.chunk_id,
                    "document_id": resp.document_id,
                    "document_name": resp.document_name,
                    "page": resp.page,
                    "section_path": resp.section_path,
                    "text": resp.text,
                    "context_before": resp.context_before,
                    "context_after": resp.context_after,
                }
            )

        return _tool_result({"error": f"Unknown tool: {name}"}, is_error=True)

    @router.post("/tools", response_model=None)
    async def tool_endpoint(request: Request):
        body = await request.json()
        req_id = body.get("id")
        method = body.get("method")
        params = body.get("params") or {}
        accept = request.headers.get("accept", "")

        if method == "tools/list":
            result = {"tools": TOOL_SCHEMAS}
            response = {"jsonrpc": "2.0", "id": req_id, "result": result}
        elif method == "tools/call":
            try:
                result = _dispatch(params)
                response = {"jsonrpc": "2.0", "id": req_id, "result": result}
            except (ChunkNotFoundError, DocumentNotFoundError, KeyError) as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": _tool_result({"error": str(exc)}, is_error=True),
                }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        if "text/event-stream" in accept:
            payload = f"data: {json.dumps(response)}\n\n"

            def stream():
                yield payload

            return StreamingResponse(stream(), media_type="text/event-stream")

        return JSONResponse(response)

    return router
