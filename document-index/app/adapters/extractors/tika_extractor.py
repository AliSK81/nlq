from __future__ import annotations

import httpx

from app.usecases.ports import ExtractedBlock, ExtractedDoc


class TikaExtractor:
    name = "tika"

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def supports(self, mime_type: str) -> bool:
        return True

    def extract(self, blob: bytes, filename: str, mime_type: str) -> ExtractedDoc:
        headers = {"Accept": "text/plain", "Content-Type": mime_type}
        with httpx.Client(timeout=self._timeout) as client:
            text_resp = client.put(f"{self._base_url}/tika", content=blob, headers=headers)
            text_resp.raise_for_status()
            text = text_resp.text.strip()

        return ExtractedDoc(
            markdown=text,
            blocks=[ExtractedBlock(text=text)] if text else [],
            page_count=None,
        )
