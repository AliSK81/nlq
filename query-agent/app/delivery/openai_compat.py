from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.graph.builder import AgentFactory
from app.usecases.parse_webui_rag import parse_messages_for_rag


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]]


class ChatCompletionRequest(BaseModel):
    model: str = "file-qa-agent"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None


def _message_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for item in content:
        if item.get("type") == "text":
            parts.append(str(item.get("text", "")))
    return "\n".join(parts)


def _build_memory_context(
    messages: list[ChatMessage],
    window: int,
) -> tuple[str, str, list[dict]]:
    if not messages:
        return "", "", []

    payload = [{"role": m.role, "content": m.content} for m in messages]
    question, prefetched_hits, memory_context = parse_messages_for_rag(payload)

    if not question:
        for msg in reversed(messages):
            if msg.role == "user":
                question, prefetched_hits, _ = parse_messages_for_rag(
                    [{"role": "user", "content": msg.content}]
                )
                if question:
                    break

    if not memory_context:
        prior = messages[:-1][-window * 2 :]
        lines = [f"{m.role}: {_message_text(m.content)}" for m in prior if _message_text(m.content)]
        memory_context = "\n".join(lines)

    return question, memory_context, prefetched_hits


def _extract_auth(request: Request) -> dict[str, str | None]:
    return {
        "cookie": request.headers.get("cookie"),
        "authorization": request.headers.get("authorization"),
        "x_auth_token": request.headers.get("x-auth-token"),
    }


def _reasoning_content(result: dict[str, Any]) -> str:
    steps = result.get("steps", [])
    timing = sum(s.get("duration_ms", 0) for s in steps)
    hits = result.get("hits") or []
    return (
        f"intent={result.get('intent')} | hits={len(hits)} | "
        f"grounded={result.get('grounded')} | steps={len(steps)} | "
        f"duration_ms={timing}"
    )


def create_openai_router(factory: AgentFactory) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/v1/models")
    def list_models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {"id": "file-qa-agent", "object": "model", "owned_by": "nlq"},
            ],
        }

    @router.post("/v1/chat/completions", response_model=None)
    async def chat_completions(
        body: ChatCompletionRequest,
        request: Request,
    ):
        question, memory_context, prefetched_hits = _build_memory_context(
            body.messages,
            settings.openai_compat_memory_window,
        )

        config = {
            "top_k": settings.agent_top_k,
            "min_score": settings.agent_min_score,
            "max_refines": settings.agent_max_refines,
        }

        try:
            result = factory.run(
                "file_qa",
                question=question,
                memory_context=memory_context,
                prefetched_hits=prefetched_hits,
                request_auth=_extract_auth(request),
                config=config,
            )
            answer = result.get("answer_text", "")
            usage_tokens = result.get("total_tokens_used", 0)
            reasoning = _reasoning_content(result)
        except Exception as exc:
            result = {}
            answer = f"Sorry, an error occurred while processing your request: {exc}"
            usage_tokens = 0
            reasoning = f"error={exc}"
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": usage_tokens}

        response_body = {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": body.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": answer,
                        "reasoning_content": reasoning,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": usage,
        }

        if body.stream:
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": body.model,
                "choices": [{"index": 0, "delta": {"content": answer}, "finish_reason": "stop"}],
            }

            def stream():
                yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(stream(), media_type="text/event-stream")

        return JSONResponse(response_body)

    return router
