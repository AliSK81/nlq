from __future__ import annotations

import re

from app.domain.intents import ClassificationOutput, Intent
from app.usecases.ports import LlmPort

GREETING_PATTERNS = re.compile(
    r"^(hi|hello|hey|سلام|درود|صبح|عصر|شب)\b",
    re.IGNORECASE,
)
FILE_QUERY_PATTERNS = re.compile(
    r"\b(document|file|pdf|report|page|section|upload|resume|reusme|cv|explain|"
    r"summarize|summary|tell me about|what does|سند|فایل|صفحه|گزارش|محتوا|رزومه|خلاصه)\b",
    re.IGNORECASE,
)
INTRO_PATTERNS = re.compile(
    r"\b(what can you|who are you|help me|capabilities|what is your model|what model|"
    r"چه کاری|چه کار|کی هستی|چه مدلی)\b",
    re.IGNORECASE,
)


def looks_like_file_query(question: str) -> bool:
    return bool(FILE_QUERY_PATTERNS.search(question))


def rule_fallback(question: str) -> ClassificationOutput:
    q = question.strip()
    if GREETING_PATTERNS.search(q):
        return ClassificationOutput(intent=Intent.CHITCHAT, message_text="Hello!")
    if INTRO_PATTERNS.search(q):
        return ClassificationOutput(intent=Intent.INTRO_CAPABILITIES)
    if looks_like_file_query(q):
        return ClassificationOutput(intent=Intent.FILE_QUERY)
    return ClassificationOutput(intent=Intent.OFF_TOPIC)


class ClassifyIntent:
    def __init__(self, llm: LlmPort) -> None:
        self._llm = llm

    def execute(self, question: str, memory_context: str = "") -> tuple[ClassificationOutput, int]:
        ruled = rule_fallback(question)
        if ruled.intent in (Intent.INTRO_CAPABILITIES, Intent.CHITCHAT, Intent.FILE_QUERY):
            return ruled, 0
        try:
            result, tokens = self._llm.classify(question, memory_context)
            if result.intent == Intent.OFF_TOPIC and looks_like_file_query(question):
                return ClassificationOutput(intent=Intent.FILE_QUERY), tokens
            return result, tokens
        except Exception:
            return ruled, 0
