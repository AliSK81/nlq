from app.domain.intents import Intent
from app.graph.nodes import GraphNodes
from app.usecases.build_answer import BuildAnswer
from app.usecases.classify import ClassifyIntent
from tests.fakes import FakeLlm, FakeRetrieval


def test_file_query_flow():
    hits = [{"document_name": "report.pdf", "page": 1, "text": "Data here", "chunk_id": "x"}]
    nodes = GraphNodes(
        ClassifyIntent(FakeLlm()),
        BuildAnswer(FakeLlm()),
        FakeLlm(),
        FakeRetrieval(hits),
    )
    state = {"question": "What does the document say about revenue?"}
    c = nodes.classify_node(state)
    assert c["intent"] == Intent.FILE_QUERY.value
    state.update(c)
    r = nodes.retrieve_node({**state, "config": {"top_k": 8, "min_score": 0.3, "max_refines": 1}})
    state.update(r)
    assert len(state["hits"]) == 1
    a = nodes.generate_answer_node(state)
    assert "document" in a["answer_text"].lower()
    assert a["grounded"] is True


def test_chitchat_flow():
    nodes = GraphNodes(
        ClassifyIntent(FakeLlm()),
        BuildAnswer(FakeLlm()),
        FakeLlm(),
        FakeRetrieval(),
    )
    state = {"question": "hello", "intent": "chitchat", "intent_message": "Hi!"}
    result = nodes.chitchat_node(state)
    assert result["success"] is True
    assert result["grounded"] is False


def test_abstain_on_empty_hits():
    nodes = GraphNodes(
        ClassifyIntent(FakeLlm()),
        BuildAnswer(FakeLlm()),
        FakeLlm(),
        FakeRetrieval([]),
    )
    state = {
        "question": "unknown topic",
        "hits": [],
        "config": {"max_refines": 0},
    }
    result = nodes.generate_answer_node(state)
    assert result["grounded"] is False
    assert "could not find" in result["answer_text"].lower()
