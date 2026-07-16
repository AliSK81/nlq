from __future__ import annotations

from app.domain.intents import ClassificationOutput, Intent
from app.usecases.ports import LlmPort


class ClassifyIntent:
    def __init__(self, llm: LlmPort) -> None:
        self._llm = llm

    def execute(self, question: str, memory_context: str = "") -> tuple[ClassificationOutput, int]:
        try:
            result, tokens = self._llm.classify(question, memory_context)
            if result.intent == Intent.OFF_TOPIC:
                return ClassificationOutput(intent=Intent.FILE_QUERY), tokens
            return result, tokens
        except Exception:
            return ClassificationOutput(intent=Intent.FILE_QUERY), 0
