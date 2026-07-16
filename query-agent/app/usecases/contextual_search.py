from __future__ import annotations

import re

CITATION_PATTERN = re.compile(r"\[([^\]]+\.(?:pdf|docx|pptx|txt|md))\]", re.IGNORECASE)


def citations_from_memory(memory_context: str) -> list[str]:
    return CITATION_PATTERN.findall(memory_context or "")


def document_ids_for_memory(memory_context: str, docs: list[dict]) -> list[str] | None:
    cited = citations_from_memory(memory_context)
    if not cited:
        return None
    ids: list[str] = []
    for cite in cited:
        cite_lower = cite.lower()
        for doc in docs:
            name = doc.get("name", "")
            if not name:
                continue
            if cite_lower in name.lower() or name.lower() in cite_lower:
                doc_id = doc.get("document_id")
                if doc_id and doc_id not in ids:
                    ids.append(doc_id)
    return ids or None


def find_document_by_name(name_hint: str | None, docs: list[dict]) -> dict | None:
    if not name_hint or not docs:
        return None
    hint = name_hint.lower().strip()
    for doc in docs:
        name = doc.get("name", "")
        if not name:
            continue
        lower = name.lower()
        if hint in lower or lower in hint:
            return doc
    return None
