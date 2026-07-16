from __future__ import annotations

import re

RAG_TASK_MARKER = re.compile(r"^### Task:", re.MULTILINE)
SOURCE_TAG = re.compile(
    r"<source\s+([^>]*)>(.*?)</source>",
    re.DOTALL | re.IGNORECASE,
)
NAME_ATTR = re.compile(r"""name=["']([^"']*)["']""", re.IGNORECASE)
ID_ATTR = re.compile(r"""id=["']([^"']*)["']""", re.IGNORECASE)


def _content_text(content: str | list) -> str:
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return str(content or "")


def _source_name(attrs: str) -> str:
    name = NAME_ATTR.search(attrs)
    if name and name.group(1).strip():
        return name.group(1).strip()
    id_match = ID_ATTR.search(attrs)
    if id_match and id_match.group(1).strip():
        return f"source-{id_match.group(1).strip()}"
    return "attached document"


def _extract_question(text: str) -> str:
    question = SOURCE_TAG.sub("", text).strip()
    question = RAG_TASK_MARKER.sub("", question).strip()
    for marker in (
        "### Guidelines:",
        "### Example of Citation:",
        "### Output:",
        "Provide a clear and direct response",
    ):
        if marker in question:
            question = question.split(marker)[0].strip()
    lines = [line.strip() for line in question.splitlines() if line.strip()]
    if lines:
        return lines[-1]
    return question.strip()


def parse_webui_message(message: str) -> tuple[str, list[dict]]:
    """Split a WebUI user message into a clean question and optional inline hits."""
    text = message.strip()
    if not text:
        return "", []

    sources = SOURCE_TAG.findall(text)
    if sources:
        hits = [
            {
                "chunk_id": f"webui-{idx}",
                "document_id": "",
                "document_name": _source_name(attrs),
                "page": None,
                "section_path": None,
                "score": 1.0,
                "text": content.strip(),
            }
            for idx, (attrs, content) in enumerate(sources, start=1)
            if content.strip()
        ]
        question = _extract_question(text)
        return question or text, hits

    if RAG_TASK_MARKER.search(text):
        return _extract_question(text) or text, []

    return text, []


def parse_messages_for_rag(messages: list[dict]) -> tuple[str, list[dict], str]:
    """Use the last user turn and collect RAG context from user/system messages."""
    last_user_idx = -1
    for i, msg in enumerate(messages):
        if msg.get("role") == "user" and _content_text(msg.get("content", "")).strip():
            last_user_idx = i

    prefetched_hits: list[dict] = []
    memory_lines: list[str] = []
    last_user_raw = ""

    for i, msg in enumerate(messages):
        role = msg.get("role", "")
        text = _content_text(msg.get("content", ""))
        if not text.strip():
            continue

        if role in ("user", "system"):
            _, hits = parse_webui_message(text)
            prefetched_hits.extend(hits)

        if i == last_user_idx:
            last_user_raw = text
        elif role in ("user", "assistant"):
            memory_lines.append(f"{role}: {text[:500]}")

    question, user_hits = parse_webui_message(last_user_raw)
    if user_hits:
        prefetched_hits = user_hits
    if not question:
        question = last_user_raw.strip()

    return question, prefetched_hits, "\n".join(memory_lines[-10:])
