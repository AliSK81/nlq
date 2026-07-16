from __future__ import annotations

from app.domain.intents import AnswerOutput
from app.usecases.ports import LlmPort

ABSTAIN_MESSAGE = (
    "I could not find relevant information in your uploaded documents to answer that question."
)
ABSTAIN_MESSAGE_FA = "نتوانستم اطلاعات مرتبطی در اسناد بارگذاری‌شده شما برای پاسخ به این سؤال پیدا کنم."


def _is_persian(text: str) -> bool:
    return any("\u0600" <= c <= "\u06ff" for c in text)


class BuildAnswer:
    def __init__(self, llm: LlmPort, min_confidence: float = 0.0) -> None:
        self._llm = llm
        self._min_confidence = min_confidence

    def execute(
        self,
        question: str,
        hits: list[dict] | None,
        memory_context: str = "",
    ) -> tuple[AnswerOutput, int, bool]:
        if not hits:
            msg = ABSTAIN_MESSAGE_FA if _is_persian(question) else ABSTAIN_MESSAGE
            return AnswerOutput(answer=msg, citations=[], confidence=0.0), 0, False

        result, tokens = self._llm.build_answer(question, hits, memory_context)
        if result.confidence < self._min_confidence:
            msg = ABSTAIN_MESSAGE_FA if _is_persian(question) else ABSTAIN_MESSAGE
            return AnswerOutput(answer=msg, citations=[], confidence=result.confidence), tokens, False

        citations = result.citations or [
            {
                "document_name": h.get("document_name"),
                "page": h.get("page"),
                "chunk_id": h.get("chunk_id"),
            }
            for h in hits[:3]
        ]
        return AnswerOutput(
            answer=result.answer,
            citations=citations,
            confidence=result.confidence,
        ), tokens, True

    @staticmethod
    def format_citations(citations: list[dict]) -> str:
        parts = []
        for c in citations:
            name = c.get("document_name", "document")
            page = c.get("page")
            if page:
                parts.append(f"[{name} p.{page}]")
            else:
                parts.append(f"[{name}]")
        return " ".join(parts)
