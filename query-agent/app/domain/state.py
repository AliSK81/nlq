from __future__ import annotations

import operator
from typing import Annotated, TypedDict


def add_int(left: int, right: int) -> int:
    return left + right


class AgentState(TypedDict, total=False):
    question: str
    memory_context: str
    request_auth: dict[str, str | None]
    config: dict
    intent: str | None
    intent_message: str | None
    hits: list[dict] | None
    prefetched_hits: list[dict] | None
    refine_count: int
    should_refine: str | None
    search_query: str | None
    answer_text: str | None
    citations: list[dict] | None
    grounded: bool
    success: bool
    error: str | None
    steps: Annotated[list[dict], operator.add]
    total_tokens_used: Annotated[int, add_int]
