from __future__ import annotations

from app.usecases.ports import SearchHit


class PassthroughReranker:
    """No-op reranker — returns hits unchanged (used when RERANKER=off)."""

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        return hits[:top_k]


class FastembedReranker:
    """Cross-encoder reranker via FastEmbed."""

    def __init__(self, model_name: str = "Xenova/ms-marco-MiniLM-L-6-v2") -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._model = TextCrossEncoder(model_name=model_name)

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        if not hits:
            return []
        scores = list(self._model.rerank(query, [h.text for h in hits]))
        paired = sorted(zip(hits, scores, strict=True), key=lambda x: float(x[1]), reverse=True)
        return [
            SearchHit(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                document_name=hit.document_name,
                page=hit.page,
                section_path=hit.section_path,
                score=float(score),
                text=hit.text,
            )
            for hit, score in paired[:top_k]
        ]
