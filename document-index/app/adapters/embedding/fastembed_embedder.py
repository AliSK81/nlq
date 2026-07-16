from __future__ import annotations

from fastembed import SparseTextEmbedding, TextEmbedding

from app.usecases.ports import Embedder, SparseEmbedding


class FastembedEmbedder:
    def __init__(
        self,
        model_name: str,
        dimension: int,
        hybrid: bool = True,
        sparse_model: str = "Qdrant/bm25",
    ) -> None:
        self._dimension = dimension
        self._model_name = model_name
        self._hybrid = hybrid
        self._use_e5_prefix = "e5" in model_name.lower()
        self._model = TextEmbedding(model_name=model_name)
        self._sparse = SparseTextEmbedding(model_name=sparse_model) if hybrid else None

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def hybrid_enabled(self) -> bool:
        return self._hybrid and self._sparse is not None

    def _prepare(self, texts: list[str], query: bool = False) -> list[str]:
        if not self._use_e5_prefix:
            return texts
        prefix = "query: " if query else "passage: "
        return [f"{prefix}{t}" for t in texts]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [list(v) for v in self._model.embed(self._prepare(texts))]

    def embed_query(self, text: str) -> list[float]:
        return list(next(self._model.embed(self._prepare([text], query=True))))

    def _to_sparse(self, embedding) -> SparseEmbedding:
        indices = [int(i) for i in embedding.indices]
        values = [float(v) for v in embedding.values]
        return SparseEmbedding(indices=indices, values=values)

    def embed_passages_sparse(self, texts: list[str]) -> list[SparseEmbedding]:
        if not self._sparse:
            return []
        return [self._to_sparse(e) for e in self._sparse.embed(texts)]

    def embed_query_sparse(self, text: str) -> SparseEmbedding | None:
        if not self._sparse:
            return None
        return self._to_sparse(next(self._sparse.embed([text])))
