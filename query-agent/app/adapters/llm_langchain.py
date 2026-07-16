from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.domain.intents import AnswerOutput, ClassificationOutput, Intent, QueryPrepOutput
from app.prompts.answer_system import ANSWER_SYSTEM
from app.prompts.answer_user import ANSWER_USER
from app.prompts.chitchat import CHITCHAT_REPLIES, CHITCHAT_WITH_DOCS
from app.prompts.classification import CLASSIFICATION_SYSTEM, CLASSIFICATION_USER
from app.prompts.query_prep import QUERY_PREP_SYSTEM, QUERY_PREP_USER
from app.usecases.context_budget import prepare_hits
from app.usecases.ports import LlmPort


def _extract_json(text: str) -> dict:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("LLM returned empty response")

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {"answer": cleaned, "citations": [], "confidence": 0.5}


def _to_answer_output(data: dict) -> AnswerOutput:
    answer = data.get("answer") or data.get("response") or ""
    answer = str(answer).strip()
    if answer.startswith("{") and '"answer"' in answer:
        try:
            nested = json.loads(answer)
            if isinstance(nested, dict) and nested.get("answer"):
                answer = str(nested["answer"]).strip()
        except json.JSONDecodeError:
            pass
    if not answer:
        raise ValueError("LLM returned empty answer")
    return AnswerOutput(
        answer=str(answer),
        citations=data.get("citations") or [],
        confidence=float(data.get("confidence") or 0.0),
    )


class LangChainLlmAdapter:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> None:
        self._llm = ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def _invoke_tokens(self, messages: list) -> tuple[str, int]:
        resp = self._llm.invoke(messages)
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        tokens = resp.usage_metadata.get("total_tokens", 0) if resp.usage_metadata else 0
        return text, tokens

    def _build_answer_messages(
        self,
        question: str,
        hits: list[dict],
        memory_context: str,
        max_context_chars: int,
    ) -> list:
        prepared_hits = prepare_hits(hits, question, max_context_chars)
        context_blocks = []
        for h in prepared_hits:
            block = (
                f"--- {h.get('document_name', 'doc')} "
                f"(page {h.get('page', '?')}, section: {h.get('section_path', '')}) ---\n"
                f"{h.get('text', '')}"
            )
            context_blocks.append(block)

        return [
            SystemMessage(content=ANSWER_SYSTEM),
            HumanMessage(
                content=ANSWER_USER.format(
                    context="\n\n".join(context_blocks),
                    memory_context=memory_context or "(none)",
                    question=question,
                )
            ),
        ]

    def classify(self, question: str, memory_context: str) -> tuple[ClassificationOutput, int]:
        messages = [
            SystemMessage(content=CLASSIFICATION_SYSTEM),
            HumanMessage(
                content=CLASSIFICATION_USER.format(
                    memory_context=memory_context or "(none)",
                    question=question,
                )
            ),
        ]
        text, tokens = self._invoke_tokens(messages)
        data = _extract_json(text)
        return ClassificationOutput(
            intent=Intent(data["intent"]),
            message_text=data.get("message_text"),
        ), tokens

    def prepare_query(
        self,
        question: str,
        memory_context: str,
        document_summary: str = "",
    ) -> tuple[QueryPrepOutput, int]:
        if not (memory_context or "").strip() and not (document_summary or "").strip():
            return QueryPrepOutput(standalone_question=question, search_query=question), 0

        messages = [
            SystemMessage(content=QUERY_PREP_SYSTEM),
            HumanMessage(
                content=QUERY_PREP_USER.format(
                    document_summary=document_summary or "(unknown)",
                    memory_context=memory_context or "(none)",
                    question=question,
                )
            ),
        ]
        text, tokens = self._invoke_tokens(messages)
        data = _extract_json(text)
        standalone = str(data.get("standalone_question") or question).strip() or question
        search = str(data.get("search_query") or standalone).strip() or standalone
        scope = str(data.get("document_scope") or "all").strip().lower()
        if scope not in ("all", "cited_only"):
            scope = "all"
        extra = data.get("extra_search_queries") or []
        if isinstance(extra, str):
            extra = [extra]
        extra_queries = [str(q).strip() for q in extra if str(q).strip()]
        multi = bool(data.get("requires_multi_document", False))
        mode = str(data.get("retrieval_mode") or "semantic").strip().lower()
        if mode not in ("semantic", "full_document"):
            mode = "semantic"
        target = data.get("target_document_name")
        target_name = str(target).strip() if target else None
        return QueryPrepOutput(
            standalone_question=standalone,
            search_query=search,
            document_scope=scope,
            extra_search_queries=extra_queries,
            requires_multi_document=multi,
            retrieval_mode=mode,
            target_document_name=target_name,
        ), tokens

    def build_answer(
        self,
        question: str,
        hits: list[dict],
        memory_context: str,
    ) -> tuple[AnswerOutput, int]:
        budgets = [
            settings.agent_max_context_chars,
            max(settings.agent_max_context_chars // 2, 4000),
        ]
        last_error: Exception | None = None

        for budget in budgets:
            try:
                messages = self._build_answer_messages(question, hits, memory_context, budget)
                text, tokens = self._invoke_tokens(messages)
                data = _extract_json(text)
                return _to_answer_output(data), tokens
            except Exception as exc:
                last_error = exc

        raise last_error or ValueError("LLM returned empty response")

    def reformulate_query(
        self,
        question: str,
        refine_count: int,
        memory_context: str = "",
    ) -> tuple[str, int]:
        messages = [
            HumanMessage(
                content=(
                    f"Rephrase this search query for document retrieval (attempt {refine_count + 1}). "
                    f"Return only the new query, no explanation.\n\n"
                    f"Conversation:\n{memory_context or '(none)'}\n\n"
                    f"Query: {question}"
                )
            ),
        ]
        text, tokens = self._invoke_tokens(messages)
        return text.strip(), tokens

    def chitchat_reply(
        self,
        intent: str,
        question: str,
        document_summary: str,
    ) -> tuple[str, int]:
        if intent == Intent.INTRO_CAPABILITIES.value:
            return CHITCHAT_REPLIES["intro_capabilities"], 0
        if (
            document_summary
            and document_summary != "(no documents indexed)"
            and intent == Intent.CHITCHAT.value
        ):
            messages = [
                HumanMessage(
                    content=CHITCHAT_WITH_DOCS.format(
                        document_summary=document_summary,
                        question=question,
                    )
                ),
            ]
            text, tokens = self._invoke_tokens(messages)
            return text.strip(), tokens
        return CHITCHAT_REPLIES.get(intent, CHITCHAT_REPLIES["off_topic"]), 0
