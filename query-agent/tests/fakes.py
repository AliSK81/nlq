from __future__ import annotations

from app.domain.intents import AnswerOutput, ClassificationOutput, Intent, QueryPrepOutput


class FakeLlm:
    def classify(self, question: str, memory_context: str):
        q = question.lower()
        if "hello" in q:
            return ClassificationOutput(intent=Intent.CHITCHAT, message_text="Hi!"), 10
        if "how many files" in q:
            return ClassificationOutput(intent=Intent.INVENTORY), 10
        if "document" in q or "revenue" in q or "experience" in q or "who is" in q:
            return ClassificationOutput(intent=Intent.FILE_QUERY), 10
        return ClassificationOutput(intent=Intent.FILE_QUERY), 10

    def prepare_query(self, question: str, memory_context: str, document_summary: str = ""):
        if not memory_context.strip() and not document_summary.strip():
            return QueryPrepOutput(standalone_question=question, search_query=question), 0
        lower = question.lower()
        if "read all" in lower or "all chunks" in lower or "full content" in lower:
            target = "Ali Ebrahimi" if "resume" in lower or "ali" in memory_context.lower() else None
            return QueryPrepOutput(
                standalone_question=question,
                search_query=question,
                document_scope="all",
                retrieval_mode="full_document",
                target_document_name=target,
            ), 5
        if "aichallenge" in lower or "ai challenge" in lower:
            return QueryPrepOutput(
                standalone_question=question,
                search_query=question,
                document_scope="all",
            ), 5
        if "growth plan" in question.lower() or "growth plan" in memory_context.lower():
            return QueryPrepOutput(
                standalone_question=(
                    "Does the Growth Plan align with Ali Ebrahimi's experience and career history?"
                    if "growth plan" in question.lower()
                    else question
                ),
                search_query="Growth Plan career development goals",
                document_scope="all",
                extra_search_queries=["Ali Ebrahimi work experience skills history"],
                requires_multi_document=True,
            ), 5
        if " he " in f" {question.lower()} " and "ali" in memory_context.lower():
            standalone = question.replace(" he ", " Ali Ebrahimi ").replace(" He ", " Ali Ebrahimi ")
            return QueryPrepOutput(
                standalone_question=standalone,
                search_query="Ali Ebrahimi work experience employment dates",
                document_scope="cited_only",
            ), 5
        if "so answer" in question.lower():
            return QueryPrepOutput(
                standalone_question="how many years of experience does Ali Ebrahimi have",
                search_query="Ali Ebrahimi work experience employment dates",
                document_scope="cited_only",
            ), 5
        return QueryPrepOutput(standalone_question=question, search_query=question), 0

    def build_answer(self, question: str, hits: list[dict], memory_context: str):
        return AnswerOutput(
            answer=f"Based on the document: {hits[0]['text']}",
            citations=[{"document_name": hits[0]["document_name"], "page": hits[0].get("page")}],
            confidence=0.9,
        ), 50

    def reformulate_query(self, question: str, refine_count: int, memory_context: str = ""):
        return f"reformulated: {question}", 5

    def chitchat_reply(self, intent: str, question: str, document_summary: str):
        return "Hello! Ask me about your documents.", 0


class FakeRetrieval:
    def __init__(self, hits: list[dict] | None = None, documents: list[dict] | None = None) -> None:
        self._hits = hits or []
        self._documents = documents
        self._calls = 0

    def search(self, query: str, top_k: int, min_score: float, auth: dict, document_ids=None):
        self._calls += 1
        if self._calls > 1 and "reformulated" in query:
            return self._hits
        if "Ali Ebrahimi" in query or "experience" in query.lower():
            return self._hits if self._hits else [
                {"document_name": "resume.pdf", "text": "Nov 2022 Present Mohaymen", "chunk_id": "1"}
            ]
        return self._hits if self._hits else []

    def list_documents(self, auth: dict):
        if self._documents is not None:
            return self._documents
        return [{"name": "report.pdf", "status": "INDEXED", "chunk_count": 1, "document_id": "d1"}]

    def list_document_chunks(self, document_id: str, auth: dict):
        return [
            {
                "chunk_id": "c1",
                "document_id": document_id,
                "document_name": "report.pdf",
                "page": 1,
                "score": 1.0,
                "text": "Full chunk text",
            }
        ]
