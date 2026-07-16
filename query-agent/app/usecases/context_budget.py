from __future__ import annotations

import re


def focus_text(text: str, question: str, limit: int) -> str:
    text = (text or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text

    lower = text.lower()
    keywords = [w for w in re.findall(r"[a-zA-Z]{4,}", question.lower())]
    anchor = -1
    for word in keywords:
        idx = lower.find(word)
        if idx >= 0 and (anchor < 0 or idx < anchor):
            anchor = idx

    if anchor < 0:
        return text[:limit] + "\n...[truncated]..."

    start = max(0, anchor - limit // 4)
    end = min(len(text), start + limit)
    snippet = text[start:end]
    if start > 0:
        snippet = "...[truncated]...\n" + snippet
    if end < len(text):
        snippet += "\n...[truncated]..."
    return snippet


def prepare_hits(hits: list[dict], question: str, max_chars: int) -> list[dict]:
    if not hits or max_chars <= 0:
        return hits

    per_hit = max(max_chars // len(hits), 1500)
    prepared: list[dict] = []
    for hit in hits:
        prepared.append({**hit, "text": focus_text(hit.get("text", ""), question, per_hit)})
    return prepared
