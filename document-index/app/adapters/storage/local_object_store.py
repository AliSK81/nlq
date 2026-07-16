from __future__ import annotations

from typing import Protocol


class ObjectStore(Protocol):
    def save(self, key: str, blob: bytes) -> str: ...

    def load(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalObjectStore:
    """Default local volume implementation."""

    def __init__(self, base_dir: str) -> None:
        self._base_dir = base_dir

    def save(self, key: str, blob: bytes) -> str:
        import os
        from pathlib import Path

        Path(self._base_dir).mkdir(parents=True, exist_ok=True)
        path = os.path.join(self._base_dir, key)
        with open(path, "wb") as f:
            f.write(blob)
        return path

    def load(self, key: str) -> bytes:
        import os

        with open(os.path.join(self._base_dir, key), "rb") as f:
            return f.read()

    def delete(self, key: str) -> None:
        import os

        path = os.path.join(self._base_dir, key)
        if os.path.exists(path):
            os.remove(path)
