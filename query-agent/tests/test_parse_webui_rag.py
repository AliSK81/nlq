from app.usecases.parse_webui_rag import parse_messages_for_rag, parse_webui_message


def test_parse_source_tags():
    message = """### Task:
Respond to the user query using the provided context.

<source id="1" name="resume.pdf">Ali Ebrahimi, Software Engineer</source>

explain this resume"""
    question, hits = parse_webui_message(message)
    assert question == "explain this resume"
    assert len(hits) == 1
    assert hits[0]["document_name"] == "resume.pdf"
    assert "Ali Ebrahimi" in hits[0]["text"]


def test_parse_source_without_name():
    message = '<source id="1">Resume body text here</source>\nexplain this resume'
    question, hits = parse_webui_message(message)
    assert question == "explain this resume"
    assert hits[0]["document_name"] == "source-1"


def test_plain_message_unchanged():
    question, hits = parse_webui_message("What is the revenue?")
    assert question == "What is the revenue?"
    assert hits == []


def test_last_user_message_with_trailing_assistant():
    messages = [
        {
            "role": "user",
            "content": (
                '### Task:\n<source id="1" name="resume.pdf">Ali Ebrahimi</source>\n'
                "explain this reusme"
            ),
        },
        {"role": "assistant", "content": ""},
    ]
    question, hits, _ = parse_messages_for_rag(messages)
    assert question == "explain this reusme"
    assert len(hits) == 1
