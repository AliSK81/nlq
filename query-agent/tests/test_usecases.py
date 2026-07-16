from app.domain.intents import Intent
from app.usecases.build_answer import BuildAnswer
from app.usecases.classify import ClassifyIntent, rule_fallback
from tests.fakes import FakeLlm, FakeRetrieval


def test_rule_fallback_greeting():
    result = rule_fallback("Hello there")
    assert result.intent == Intent.CHITCHAT


def test_rule_fallback_file_query():
    result = rule_fallback("What does the report say about revenue?")
    assert result.intent == Intent.FILE_QUERY


def test_classify_with_fake_llm():
    classify = ClassifyIntent(FakeLlm())
    result, tokens = classify.execute("hello")
    assert result.intent == Intent.CHITCHAT
    assert tokens == 10


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
