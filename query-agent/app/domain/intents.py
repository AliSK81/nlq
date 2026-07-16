from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Intent(str, Enum):
    CHITCHAT = "chitchat"
    INTRO_CAPABILITIES = "intro_capabilities"
    FILE_QUERY = "file_query"
    OFF_TOPIC = "off_topic"


class ClassificationOutput(BaseModel):
    intent: Intent
    message_text: str | None = None


class AnswerOutput(BaseModel):
    answer: str
    citations: list[dict] = Field(default_factory=list)
    confidence: float = 0.0
