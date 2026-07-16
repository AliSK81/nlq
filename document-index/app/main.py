from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.chunking.chonkie_chunker import ChonkieChunker
from app.adapters.embedding.fastembed_embedder import FastembedEmbedder
from app.adapters.extractors.docling_extractor import DoclingExtractor
from app.adapters.extractors.tika_extractor import TikaExtractor
from app.adapters.reranker.passthrough_reranker import FastembedReranker, PassthroughReranker
from app.adapters.repo.postgres_document_repo import PostgresDocumentRepo
from app.adapters.vector.qdrant_index import QdrantIndex
from app.config import settings
from app.delivery.rest import create_rest_router
from app.delivery.tool_rpc import create_tool_router
from app.delivery.worker import IngestionWorker
from app.usecases.fetch_chunk import FetchChunk
from app.usecases.ingest_document import IngestDocument
from app.usecases.list_documents import ListDocuments
from app.usecases.search_documents import SearchDocuments

_worker: IngestionWorker | None = None


def _build_extractor():
    if settings.extractor == "tika":
        return TikaExtractor(settings.tika_url)
    return DoclingExtractor(settings.docling_url)


def _build_reranker():
    if settings.reranker in ("off", "none", "passthrough"):
        return PassthroughReranker()
    return FastembedReranker(settings.reranker_model)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker
    repo = PostgresDocumentRepo(settings.database_url)
    extractor = _build_extractor()
    chunker = ChonkieChunker(settings.chunk_target_tokens, settings.chunk_overlap_tokens)
    embedder = FastembedEmbedder(
        settings.embedding_model,
        settings.embedding_dim,
        hybrid=settings.hybrid_search,
        sparse_model=settings.sparse_embedding_model,
    )
    vector_index = QdrantIndex(
        settings.qdrant_url,
        settings.qdrant_collection,
        settings.embedding_dim,
        hybrid=settings.hybrid_search,
    )
    vector_index.ensure_collection()
    reranker = _build_reranker()

    ingest = IngestDocument(repo, settings.upload_dir, settings.max_upload_mb)
    search = SearchDocuments(
        embedder,
        vector_index,
        reranker=reranker,
        candidate_multiplier=settings.rerank_candidate_multiplier,
    )
    list_docs = ListDocuments(repo)
    fetch_chunk = FetchChunk(repo)

    app.include_router(create_rest_router(ingest, list_docs, fetch_chunk, search, repo, vector_index))
    app.include_router(create_tool_router(search, list_docs, fetch_chunk, repo))

    _worker = IngestionWorker(
        repo, extractor, chunker, embedder, vector_index,
        settings.upload_dir, settings.ingest_worker_concurrency,
    )
    _worker.start()
    yield
    if _worker:
        _worker.stop()


app = FastAPI(title="Document Index", lifespan=lifespan)
