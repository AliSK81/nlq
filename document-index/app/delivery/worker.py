from __future__ import annotations

import glob
import logging
import os
import threading
import time

from app.domain.document import DocumentId, IngestionStatus
from app.usecases.ports import Chunker, DocumentRepo, Embedder, Extractor, VectorIndex

logger = logging.getLogger(__name__)


class IngestionWorker:
    def __init__(
        self,
        repo: DocumentRepo,
        extractor: Extractor,
        chunker: Chunker,
        embedder: Embedder,
        vector_index: VectorIndex,
        upload_dir: str,
        concurrency: int = 2,
    ) -> None:
        self._repo = repo
        self._extractor = extractor
        self._chunker = chunker
        self._embedder = embedder
        self._vector_index = vector_index
        self._upload_dir = upload_dir
        self._concurrency = concurrency
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for _ in range(self._concurrency):
            t = threading.Thread(target=self._loop, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            doc_id = self._repo.claim_pending_job()
            if not doc_id:
                time.sleep(1)
                continue
            try:
                self._process(doc_id)
            except Exception as exc:
                logger.exception("Ingestion failed for %s", doc_id)
                doc = self._repo.get(doc_id)
                if doc:
                    doc.transition_to(IngestionStatus.FAILED)
                    doc.error = str(exc)
                    self._repo.update(doc)
                self._repo.mark_job_failed(doc_id, str(exc))

    def _find_file(self, doc_id: DocumentId) -> tuple[str, bytes]:
        pattern = os.path.join(self._upload_dir, f"{doc_id}_*")
        matches = glob.glob(pattern)
        if not matches:
            raise FileNotFoundError(f"No upload file for document {doc_id}")
        path = matches[0]
        with open(path, "rb") as f:
            return path, f.read()

    def _process(self, doc_id: DocumentId) -> None:
        doc = self._repo.get(doc_id)
        if not doc:
            return

        doc.transition_to(IngestionStatus.EXTRACTING)
        doc.extractor = self._extractor.name
        self._repo.update(doc)

        _, blob = self._find_file(doc_id)
        extracted = self._extractor.extract(blob, doc.name, doc.mime_type)
        doc.page_count = extracted.page_count
        self._repo.update(doc)

        doc.transition_to(IngestionStatus.CHUNKING)
        self._repo.update(doc)
        chunks = self._chunker.chunk(extracted, doc_id, doc.tenant_id)

        doc.transition_to(IngestionStatus.EMBEDDING)
        self._repo.update(doc)
        vectors = self._embedder.embed_passages([c.text for c in chunks])

        self._vector_index.upsert_chunks(chunks, vectors, doc.name)
        self._repo.save_chunks(chunks)

        doc.transition_to(IngestionStatus.INDEXED)
        self._repo.update(doc)
        logger.info("Indexed document %s with %d chunks", doc_id, len(chunks))
