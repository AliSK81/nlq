from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.chunking.hybrid_chunker import HybridChunker
from app.adapters.embedding.fastembed_embedder import FastembedEmbedder
from app.adapters.extractors.docling_extractor import DoclingExtractor
from app.adapters.extractors.tika_extractor import TikaExtractor
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker
    repo = PostgresDocumentRepo(settings.database_url)
    extractor = _build_extractor()
    chunker = HybridChunker(settings.chunk_target_tokens, settings.chunk_overlap_tokens)
    embedder = FastembedEmbedder(settings.embedding_model, settings.embedding_dim)
    vector_index = QdrantIndex(settings.qdrant_url, settings.qdrant_collection, settings.embedding_dim)
    vector_index.ensure_collection()

    ingest = IngestDocument(repo, settings.upload_dir, settings.max_upload_mb)
    search = SearchDocuments(embedder, vector_index)
    list_docs = ListDocuments(repo)
    fetch_chunk = FetchChunk(repo)

    app.include_router(create_rest_router(ingest, list_docs, fetch_chunk, repo, vector_index))
    app.include_router(create_tool_router(search, list_docs, fetch_chunk))

    _worker = IngestionWorker(
        repo, extractor, chunker, embedder, vector_index,
        settings.upload_dir, settings.ingest_worker_concurrency,
    )
    _worker.start()
    yield
    if _worker:
        _worker.stop()


app = FastAPI(title="Document Index", lifespan=lifespan)
