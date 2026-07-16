from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.conversation_history import ConversationHistoryManager
from app.adapters.document_index_client import DocumentIndexClient
from app.adapters.llm_langchain import LangChainLlmAdapter
from app.config import settings
from app.delivery.ask import create_ask_router
from app.delivery.openai_compat import create_openai_router
from app.graph.builder import AgentFactory, build_graph
from app.graph.nodes import GraphNodes
from app.observability import create_langfuse_handler, setup_observability
from app.usecases.build_answer import BuildAnswer
from app.usecases.classify import ClassifyIntent


@asynccontextmanager
async def lifespan(app: FastAPI):
    langfuse_handler = create_langfuse_handler()
    callbacks = [langfuse_handler] if langfuse_handler else None
    llm = LangChainLlmAdapter(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
        callbacks=callbacks,
    )
    retrieval = DocumentIndexClient(
        base_url=settings.document_index_url,
        api_version=settings.document_index_api_version,
        timeout=settings.document_index_timeout,
    )
    classify = ClassifyIntent(llm)
    build_answer = BuildAnswer(llm, min_confidence=settings.agent_min_confidence)
    nodes = GraphNodes(classify, build_answer, llm, retrieval)
    compiled = build_graph(nodes)
    factory = AgentFactory(compiled)

    app.include_router(create_openai_router(factory))

    history = ConversationHistoryManager(settings.database_url)
    app.include_router(create_ask_router(factory, history))

    app.state.agent_factory = factory
    if langfuse_handler:
        app.state.langfuse_handler = langfuse_handler
    yield


app = FastAPI(title="Query Agent", lifespan=lifespan)
setup_observability(app)
