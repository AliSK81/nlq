from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Intent(str, Enum):
    CHITCHAT = "chitchat"
    INTRO_CAPABILITIES = "intro_capabilities"
    FILE_QUERY = "file_query"
    INVENTORY = "inventory"
    OFF_TOPIC = "off_topic"


class QueryPrepOutput(BaseModel):
    standalone_question: str
    search_query: str
    document_scope: str = "all"
    extra_search_queries: list[str] = Field(default_factory=list)
    requires_multi_document: bool = False
    retrieval_mode: str = "semantic"
    target_document_name: str | None = None


class ClassificationOutput(BaseModel):
    intent: Intent
    message_text: str | None = None


class AnswerOutput(BaseModel):
    answer: str
    citations: list[dict] = Field(default_factory=list)
    confidence: float = 0.0
