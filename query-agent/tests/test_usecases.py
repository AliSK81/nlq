from app.domain.intents import Intent
from app.usecases.build_answer import BuildAnswer
from app.usecases.classify import ClassifyIntent
from app.usecases.contextual_search import citations_from_memory, document_ids_for_memory
from tests.fakes import FakeLlm, FakeRetrieval


def test_classify_with_fake_llm():
    classify = ClassifyIntent(FakeLlm())
    result, tokens = classify.execute("hello")
    assert result.intent == Intent.CHITCHAT
    assert tokens == 10


def test_classify_inventory_with_fake_llm():
    classify = ClassifyIntent(FakeLlm())
    result, _ = classify.execute("how many files are uploaded?")
    assert result.intent == Intent.INVENTORY


def test_build_answer_with_hits():
    hits = [{"document_name": "report.pdf", "page": 4, "text": "Revenue up 20%", "chunk_id": "c1"}]
    answer, tokens, grounded = BuildAnswer(FakeLlm()).execute("What is revenue?", hits)
    assert grounded is True
    assert "Revenue" in answer.answer
    assert tokens == 50


def test_build_answer_abstain():
    answer, tokens, grounded = BuildAnswer(FakeLlm()).execute("What is revenue?", [])
    assert grounded is False
    assert "could not find" in answer.answer.lower()


def test_build_answer_low_confidence_abstains():
    class LowConfidenceLlm(FakeLlm):
        def build_answer(self, question, hits, memory_context):
            from app.domain.intents import AnswerOutput

            return AnswerOutput(answer="maybe", citations=[], confidence=0.1), 10

    hits = [{"document_name": "report.pdf", "page": 1, "text": "x", "chunk_id": "c1"}]
    answer, tokens, grounded = BuildAnswer(LowConfidenceLlm(), min_confidence=0.3).execute(
        "What is revenue?", hits
    )
    assert grounded is False
    assert "could not find" in answer.answer.lower()
