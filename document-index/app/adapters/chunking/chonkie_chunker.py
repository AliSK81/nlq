from __future__ import annotations

from chonkie import RecursiveChunker, TokenChunker

from app.domain.chunk import Chunk
from app.domain.document import DocumentId
from app.usecases.ports import ExtractedBlock, ExtractedDoc


class ChonkieChunker:
    """OSS chunker via Chonkie. Used for Tika plain text and as Docling-serve fallback."""

    def __init__(self, target_tokens: int = 512, overlap_tokens: int = 64) -> None:
        self._target = target_tokens
        self._overlap = overlap_tokens
        self._token = TokenChunker(chunk_size=target_tokens, chunk_overlap=overlap_tokens)
        self._recursive = RecursiveChunker(chunk_size=target_tokens)

    def chunk(self, doc: ExtractedDoc, document_id: DocumentId, tenant_id: str) -> list[Chunk]:
        segments = doc.blocks if doc.blocks else [ExtractedBlock(text=doc.markdown)]
        chunks: list[Chunk] = []
        ordinal = 0

        for block in segments:
            text = block.text.strip()
            if not text:
                continue
            # Prefer recursive (structure-aware) for longer markdown blocks; token for short.
            pieces = (
                self._recursive.chunk(text)
                if len(text.split()) > self._target // 2
                else self._token.chunk(text)
            )
            for piece in pieces:
                piece_text = piece.text.strip() if hasattr(piece, "text") else str(piece).strip()
                if not piece_text:
                    continue
                token_count = getattr(piece, "token_count", None) or max(1, len(piece_text.split()))
                chunks.append(
                    Chunk(
                        id=Chunk.new_id(),
                        document_id=document_id,
                        tenant_id=tenant_id,
                        ordinal=ordinal,
                        text=piece_text,
                        section_path=block.section_path,
                        page=block.page,
                        token_count=int(token_count),
                    )
                )
                ordinal += 1

        if not chunks and doc.markdown.strip():
            for piece in self._token.chunk(doc.markdown.strip()):
                piece_text = piece.text.strip() if hasattr(piece, "text") else str(piece).strip()
                if not piece_text:
                    continue
                chunks.append(
                    Chunk(
                        id=Chunk.new_id(),
                        document_id=document_id,
                        tenant_id=tenant_id,
                        ordinal=ordinal,
                        text=piece_text,
                        token_count=getattr(piece, "token_count", len(piece_text.split())),
                    )
                )
                ordinal += 1
        return chunks


# Back-compat alias for imports that still expect HybridChunker name.
HybridChunker = ChonkieChunker
