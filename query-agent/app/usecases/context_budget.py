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

    prefix = "...[truncated]...\n"
    suffix = "\n...[truncated]..."

    if anchor < 0:
        body_limit = max(0, limit - len(suffix))
        return text[:body_limit] + suffix

    start = max(0, anchor - limit // 4)
    end = min(len(text), start + limit)
    needs_prefix = start > 0
    needs_suffix = end < len(text)
    overhead = (len(prefix) if needs_prefix else 0) + (len(suffix) if needs_suffix else 0)
    body_limit = max(0, limit - overhead)
    end = min(len(text), start + body_limit)
    snippet = text[start:end]
    if needs_prefix:
        snippet = prefix + snippet
    if end < len(text):
        snippet += suffix
    return snippet


def prepare_hits(hits: list[dict], question: str, max_chars: int) -> list[dict]:
    if not hits or max_chars <= 0:
        return hits

    per_hit = max(max_chars // len(hits), 1500)
    prepared: list[dict] = []
    for hit in hits:
        prepared.append({**hit, "text": focus_text(hit.get("text", ""), question, per_hit)})
    return prepared
