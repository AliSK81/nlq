from __future__ import annotations

from fastembed import TextEmbedding

from app.usecases.ports import Embedder


class FastembedEmbedder:
    def __init__(self, model_name: str, dimension: int) -> None:
        self._dimension = dimension
        self._model_name = model_name
        self._use_e5_prefix = "e5" in model_name.lower()
        self._model = TextEmbedding(model_name=model_name)

    @property
    def dimension(self) -> int:
        return self._dimension

    def _prepare(self, texts: list[str], query: bool = False) -> list[str]:
        if not self._use_e5_prefix:
            return texts
        prefix = "query: " if query else "passage: "
        return [f"{prefix}{t}" for t in texts]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [list(v) for v in self._model.embed(self._prepare(texts))]

    def embed_query(self, text: str) -> list[float]:
        return list(next(self._model.embed(self._prepare([text], query=True))))
