from __future__ import annotations

import tiktoken

from app.domain.chunk import Chunk
from app.domain.document import DocumentId
from app.usecases.ports import Chunker, ExtractedBlock, ExtractedDoc


class HybridChunker:
    def __init__(self, target_tokens: int = 512, overlap_tokens: int = 64) -> None:
        self._target = target_tokens
        self._overlap = overlap_tokens
        self._enc = tiktoken.get_encoding("cl100k_base")

    def chunk(self, doc: ExtractedDoc, document_id: DocumentId, tenant_id: str) -> list[Chunk]:
        segments = doc.blocks if doc.blocks else [ExtractedBlock(text=doc.markdown)]
        chunks: list[Chunk] = []
        ordinal = 0

        for block in segments:
            text = block.text.strip()
            if not text:
                continue
            tokens = self._enc.encode(text)
            start = 0
            while start < len(tokens):
                end = min(start + self._target, len(tokens))
                piece = self._enc.decode(tokens[start:end])
                chunk = Chunk(
                    id=Chunk.new_id(),
                    document_id=document_id,
                    tenant_id=tenant_id,
                    ordinal=ordinal,
                    text=piece,
                    section_path=block.section_path,
                    page=block.page,
                    token_count=end - start,
                )
                chunks.append(chunk)
                ordinal += 1
                if end >= len(tokens):
                    break
                start = max(end - self._overlap, start + 1)

        if not chunks and doc.markdown.strip():
            chunks.append(
                Chunk(
                    id=Chunk.new_id(),
                    document_id=document_id,
                    tenant_id=tenant_id,
                    ordinal=0,
                    text=doc.markdown.strip(),
                    token_count=len(self._enc.encode(doc.markdown)),
                )
            )
        return chunks
