from __future__ import annotations

from app.domain.intents import AnswerOutput, ClassificationOutput, Intent


class FakeLlm:
    def classify(self, question: str, memory_context: str):
        if "hello" in question.lower():
            return ClassificationOutput(intent=Intent.CHITCHAT, message_text="Hi!"), 10
        if "document" in question.lower() or "revenue" in question.lower():
            return ClassificationOutput(intent=Intent.FILE_QUERY), 10
        return ClassificationOutput(intent=Intent.OFF_TOPIC), 10

    def build_answer(self, question: str, hits: list[dict], memory_context: str):
        return AnswerOutput(
            answer=f"Based on the document: {hits[0]['text']}",
            citations=[{"document_name": hits[0]["document_name"], "page": hits[0].get("page")}],
            confidence=0.9,
        ), 50

    def reformulate_query(self, question: str, refine_count: int):
        return f"reformulated: {question}", 5

    def chitchat_reply(self, intent: str, question: str, document_summary: str):
        return "Hello! Ask me about your documents.", 0


class FakeRetrieval:
    def __init__(self, hits: list[dict] | None = None) -> None:
        self._hits = hits or []
        self._calls = 0

    def search(self, query: str, top_k: int, min_score: float, auth: dict):
        self._calls += 1
        if self._calls > 1 and "reformulated" in query:
            return self._hits
        return self._hits if self._hits else []

    def list_documents(self, auth: dict):
        return [{"name": "report.pdf", "status": "INDEXED"}]
