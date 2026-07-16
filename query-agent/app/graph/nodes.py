from __future__ import annotations

import time
from typing import Any

from app.domain.intents import Intent
from app.domain.state import AgentState
from app.usecases.build_answer import BuildAnswer
from app.usecases.classify import ClassifyIntent
from app.usecases.ports import LlmPort, RetrievalPort


class GraphNodes:
    def __init__(
        self,
        classify: ClassifyIntent,
        build_answer: BuildAnswer,
        llm: LlmPort,
        retrieval: RetrievalPort,
    ) -> None:
        self._classify = classify
        self._build_answer = build_answer
        self._llm = llm
        self._retrieval = retrieval

    def classify_node(self, state: AgentState) -> dict[str, Any]:
        start = time.monotonic()
        if state.get("prefetched_hits"):
            duration = int((time.monotonic() - start) * 1000)
            return {
                "intent": Intent.FILE_QUERY.value,
                "intent_message": None,
                "total_tokens_used": 0,
                "steps": [{"node": "classify", "success": True, "duration_ms": duration}],
            }
        result, tokens = self._classify.execute(
            state["question"],
            state.get("memory_context", ""),
        )
        duration = int((time.monotonic() - start) * 1000)
        return {
            "intent": result.intent.value,
            "intent_message": result.message_text,
            "total_tokens_used": tokens,
            "steps": [{"node": "classify", "success": True, "duration_ms": duration}],
        }

    def chitchat_node(self, state: AgentState) -> dict[str, Any]:
        start = time.monotonic()
        intent = state.get("intent", Intent.OFF_TOPIC.value)
        try:
            docs = self._retrieval.list_documents(state.get("request_auth", {}))
        except Exception:
            docs = []
        summary = ", ".join(d.get("name", "") for d in docs[:10]) or "(no documents indexed)"
        if state.get("intent_message") and intent == Intent.CHITCHAT.value:
            text, tokens = state["intent_message"], 0
        else:
            text, tokens = self._llm.chitchat_reply(intent, state["question"], summary)
        duration = int((time.monotonic() - start) * 1000)
        return {
            "answer_text": text,
            "success": True,
            "grounded": False,
            "total_tokens_used": tokens,
            "steps": [{"node": "chitchat", "success": True, "duration_ms": duration}],
        }

    def retrieve_node(self, state: AgentState) -> dict[str, Any]:
        start = time.monotonic()
        config = state.get("config", {})
        query = state.get("search_query") or state["question"]
        refine_count = state.get("refine_count", 0)

        try:
            hits = self._retrieval.search(
                query=query,
                top_k=config.get("top_k", 8),
                min_score=config.get("min_score", 0.3),
                auth=state.get("request_auth", {}),
            )
        except Exception:
            hits = []

        if not hits:
            hits = list(state.get("prefetched_hits") or [])

        tokens = 0
        should_refine = "done"
        new_refine_count = refine_count
        new_query = query

        if not hits and refine_count < config.get("max_refines", 1):
            new_query, tokens = self._llm.reformulate_query(state["question"], refine_count)
            should_refine = "refine"
            new_refine_count = refine_count + 1

        duration = int((time.monotonic() - start) * 1000)
        return {
            "hits": hits,
            "search_query": new_query,
            "should_refine": should_refine,
            "refine_count": new_refine_count,
            "total_tokens_used": tokens,
            "steps": [{"node": "retrieve", "success": True, "duration_ms": duration, "hits": len(hits)}],
        }

    def generate_answer_node(self, state: AgentState) -> dict[str, Any]:
        start = time.monotonic()
        result, tokens, grounded = self._build_answer.execute(
            state["question"],
            state.get("hits"),
            state.get("memory_context", ""),
        )
        citation_suffix = ""
        if result.citations:
            citation_suffix = "\n\n" + BuildAnswer.format_citations(result.citations)
        duration = int((time.monotonic() - start) * 1000)
        return {
            "answer_text": result.answer + citation_suffix,
            "citations": result.citations,
            "grounded": grounded,
            "success": True,
            "total_tokens_used": tokens,
            "steps": [{"node": "generate_answer", "success": True, "duration_ms": duration}],
        }
