from __future__ import annotations

from app.domain.intents import Intent
from app.domain.state import AgentState


def route_after_classify(state: AgentState) -> str:
    intent = state.get("intent", Intent.OFF_TOPIC.value)
    if intent == Intent.FILE_QUERY.value:
        return "retrieve"
    return "chitchat"


def route_after_retrieve(state: AgentState) -> str:
    hits = state.get("hits") or []
    if hits:
        return "generate_answer"
    if state.get("should_refine") == "refine":
        return "retrieve"
    return "generate_answer"
