from app.usecases.contextual_search import citations_from_memory, document_ids_for_memory


def test_citations_from_memory():
    memory = "assistant: answer text [Ali Ebrahimi - Resume.pdf]"
    assert citations_from_memory(memory) == ["Ali Ebrahimi - Resume.pdf"]


def test_document_ids_for_memory():
    memory = "assistant: see [report.pdf]"
    docs = [{"document_id": "abc", "name": "report.pdf"}]
    assert document_ids_for_memory(memory, docs) == ["abc"]
