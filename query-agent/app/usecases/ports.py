from __future__ import annotations

from typing import Protocol

from app.domain.intents import AnswerOutput, ClassificationOutput


class LlmPort(Protocol):
    def classify(self, question: str, memory_context: str) -> tuple[ClassificationOutput, int]: ...

    def build_answer(
        self,
        question: str,
        hits: list[dict],
        memory_context: str,
    ) -> tuple[AnswerOutput, int]: ...

    def reformulate_query(self, question: str, refine_count: int) -> tuple[str, int]: ...

    def chitchat_reply(
        self,
        intent: str,
        question: str,
        document_summary: str,
    ) -> tuple[str, int]: ...


class RetrievalPort(Protocol):
    def search(
        self,
        query: str,
        top_k: int,
        min_score: float,
        auth: dict[str, str | None],
    ) -> list[dict]: ...

    def list_documents(self, auth: dict[str, str | None]) -> list[dict]: ...
