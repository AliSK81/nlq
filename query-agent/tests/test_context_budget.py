from app.adapters.llm_langchain import _extract_json, _to_answer_output
from app.usecases.context_budget import focus_text, prepare_hits


def test_extract_json_plain_text_fallback():
    data = _extract_json("The Pattern Selection Guide maps questions to patterns.")
    assert "Pattern Selection Guide" in data["answer"]


def test_extract_json_object():
    data = _extract_json('{"answer":"ok","citations":[],"confidence":0.8}')
    assert data["answer"] == "ok"


def test_to_answer_output_rejects_empty():
    try:
        _to_answer_output({"answer": "   "})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_focus_text_finds_keyword_window():
    text = "aaa " * 1000 + "Pattern Selection Guide details here " + "bbb " * 1000
    snippet = focus_text(text, "Pattern Selection Guide", 500)
    assert "Pattern Selection Guide" in snippet
    assert len(snippet) <= 500


def test_prepare_hits_splits_budget():
    hits = [
        {"text": "x" * 8000, "document_name": "a.pdf"},
        {"text": "y" * 8000, "document_name": "b.pdf"},
    ]
    prepared = prepare_hits(hits, "Pattern Selection Guide", 12000)
    assert len(prepared) == 2
    assert all(len(h["text"]) <= 6200 for h in prepared)
