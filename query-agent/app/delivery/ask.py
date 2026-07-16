from __future__ import annotations

from pydantic import BaseModel, Field

from app.adapters.conversation_history import ConversationHistoryManager
from app.config import settings
from app.graph.builder import AgentFactory


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None
    username: str | None = None


class AskResponse(BaseModel):
    session_id: str
    answer: str
    intent: str | None = None
    citations: list[dict] = Field(default_factory=list)
    grounded: bool = False
    tokens_used: int = 0


def create_ask_router(factory: AgentFactory, history: ConversationHistoryManager):
    from fastapi import APIRouter

    router = APIRouter()

    @router.post("/ask")
    def ask(body: AskRequest) -> AskResponse:
        session_id = body.session_id or history.create_session(body.username)
        memory_context = history.get_memory_context(session_id, settings.openai_compat_memory_window)

        config = {
            "top_k": settings.agent_top_k,
            "min_score": settings.agent_min_score,
            "max_refines": settings.agent_max_refines,
        }

        result = factory.run(
            "file_qa",
            question=body.question,
            memory_context=memory_context,
            request_auth={},
            config=config,
        )

        answer = result.get("answer_text", "")
        tokens = result.get("total_tokens_used", 0)

        history.save_message(session_id, "user", body.question)
        history.save_message(
            session_id,
            "assistant",
            answer,
            intent=result.get("intent"),
            citations=result.get("citations"),
            tokens_used=tokens,
        )

        return AskResponse(
            session_id=session_id,
            answer=answer,
            intent=result.get("intent"),
            citations=result.get("citations") or [],
            grounded=result.get("grounded", False),
            tokens_used=tokens,
        )

    return router
