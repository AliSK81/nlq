from __future__ import annotations

import time
from typing import Any

from app.domain.intents import Intent, QueryPrepOutput
from app.domain.state import AgentState
from app.usecases.build_answer import BuildAnswer
from app.usecases.classify import ClassifyIntent
from app.usecases.contextual_search import (
    citations_from_memory,
    document_ids_for_memory,
    find_document_by_name,
)
from app.usecases.ports import LlmPort, RetrievalPort


def _merge_hits(hit_lists: list[list[dict]], top_k: int) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for hits in hit_lists:
        for hit in hits:
            chunk_id = str(hit.get("chunk_id", ""))
            if chunk_id and chunk_id in seen:
                continue
            if chunk_id:
                seen.add(chunk_id)
            merged.append(hit)
    merged.sort(key=lambda h: h.get("score") or 0, reverse=True)
    return merged[:top_k]


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

        if intent == Intent.INVENTORY.value:
            if not docs:
                text = "No documents are indexed yet. Upload a file and wait until status is INDEXED."
            else:
                lines = [f"You have **{len(docs)}** indexed document(s):"]
                for doc in docs:
                    chunks = doc.get("chunk_count", 0)
                    lines.append(f"- {doc.get('name', 'unknown')} ({chunks} chunks)")
                text = "\n".join(lines)
            tokens = 0
        elif state.get("intent_message") and intent == Intent.CHITCHAT.value:
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

    def _search(
        self,
        queries: list[str],
        *,
        top_k: int,
        min_score: float,
        auth: dict,
        document_ids: list[str] | None,
    ) -> list[dict]:
        hit_lists: list[list[dict]] = []
        for query in queries:
            try:
                hit_lists.append(
                    self._retrieval.search(
                        query=query,
                        top_k=top_k,
                        min_score=min_score,
                        auth=auth,
                        document_ids=document_ids,
                    )
                )
            except Exception:
                continue
        return _merge_hits(hit_lists, top_k)

    def retrieve_node(self, state: AgentState) -> dict[str, Any]:
        start = time.monotonic()
        config = state.get("config", {})
        memory = state.get("memory_context", "")
        auth = state.get("request_auth", {})
        refine_count = state.get("refine_count", 0)
        top_k = config.get("top_k", 8)
        min_score = config.get("min_score", 0.3)
        tokens = 0

        docs: list[dict] = []
        try:
            docs = self._retrieval.list_documents(auth)
        except Exception:
            pass
        document_summary = ", ".join(d.get("name", "") for d in docs[:20]) or "(none)"

        prepared = QueryPrepOutput(
            standalone_question=state["question"],
            search_query=state.get("search_query") or state["question"],
        )
        if not state.get("search_query"):
            if memory.strip() or document_summary != "(none)":
                prepared, prep_tokens = self._llm.prepare_query(
                    state["question"],
                    memory,
                    document_summary,
                )
                tokens += prep_tokens
            else:
                prepared = QueryPrepOutput(
                    standalone_question=state["question"],
                    search_query=state["question"],
                )

        effective_question = prepared.standalone_question
        retrieval_mode = prepared.retrieval_mode
        hits: list[dict] = []

        if prepared.retrieval_mode == "full_document":
            target = find_document_by_name(prepared.target_document_name, docs)
            if not target:
                cited = citations_from_memory(memory)
                if cited:
                    target = find_document_by_name(cited[-1], docs)
            if target:
                try:
                    hits = self._retrieval.list_document_chunks(target["document_id"], auth)
                except Exception:
                    hits = []
        else:
            doc_ids: list[str] | None = None
            if prepared.document_scope == "cited_only":
                doc_ids = document_ids_for_memory(memory, docs)

            queries = [prepared.search_query, *prepared.extra_search_queries]
            hits = self._search(
                queries,
                top_k=top_k,
                min_score=min_score,
                auth=auth,
                document_ids=doc_ids,
            )

            if prepared.requires_multi_document:
                doc_names = {h.get("document_name") for h in hits if h.get("document_name")}
                if len(doc_names) < 2:
                    supplemental = self._search(
                        [effective_question, *prepared.extra_search_queries],
                        top_k=top_k,
                        min_score=min_score,
                        auth=auth,
                        document_ids=None,
                    )
                    hits = _merge_hits([hits, supplemental], top_k)

            if not hits:
                hits = self._search(
                    queries,
                    top_k=top_k,
                    min_score=max(min_score * 0.5, 0.12),
                    auth=auth,
                    document_ids=None,
                )

        if not hits:
            hits = list(state.get("prefetched_hits") or [])

        should_refine = "done"
        new_refine_count = refine_count
        new_query = prepared.search_query

        if not hits and refine_count < config.get("max_refines", 1):
            new_query, refine_tokens = self._llm.reformulate_query(
                effective_question,
                refine_count,
                memory,
            )
            tokens += refine_tokens
            should_refine = "refine"
            new_refine_count = refine_count + 1

        duration = int((time.monotonic() - start) * 1000)
        return {
            "hits": hits,
            "search_query": new_query,
            "effective_question": effective_question,
            "retrieval_mode": retrieval_mode,
            "should_refine": should_refine,
            "refine_count": new_refine_count,
            "total_tokens_used": tokens,
            "steps": [{"node": "retrieve", "success": True, "duration_ms": duration, "hits": len(hits)}],
        }

    def generate_answer_node(self, state: AgentState) -> dict[str, Any]:
        start = time.monotonic()
        question = state.get("effective_question") or state["question"]
        hits = state.get("hits") or []

        if state.get("retrieval_mode") == "full_document" and hits:
            doc_name = hits[0].get("document_name", "document")
            sections = [f"### Part {i}\n{h.get('text', '').strip()}" for i, h in enumerate(hits, 1)]
            answer = f"Full content of **{doc_name}** ({len(hits)} parts):\n\n" + "\n\n".join(sections)
            citations = [{"document_name": doc_name, "page": h.get("page"), "chunk_id": h.get("chunk_id")} for h in hits[:3]]
            duration = int((time.monotonic() - start) * 1000)
            suffix = "\n\n" + BuildAnswer.format_citations(citations) if citations else ""
            return {
                "answer_text": answer + suffix,
                "citations": citations,
                "grounded": True,
                "success": True,
                "total_tokens_used": 0,
                "steps": [{"node": "generate_answer", "success": True, "duration_ms": duration}],
            }

        result, tokens, grounded = self._build_answer.execute(
            question,
            hits,
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
