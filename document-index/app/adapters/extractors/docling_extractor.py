from __future__ import annotations

import httpx

from app.usecases.ports import ExtractedBlock, ExtractedDoc

SUPPORTED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/html",
    "text/plain",
    "text/markdown",
    "image/png",
    "image/jpeg",
    "image/tiff",
}


class DoclingExtractor:
    name = "docling"

    def __init__(self, base_url: str, timeout: float = 300.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def supports(self, mime_type: str) -> bool:
        return mime_type in SUPPORTED_MIMES or mime_type.startswith("text/")

    def extract(self, blob: bytes, filename: str, mime_type: str) -> ExtractedDoc:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                f"{self._base_url}/v1/convert/file",
                files={"files": (filename, blob, mime_type)},
            )
            response.raise_for_status()
            data = response.json()

        doc_data = data.get("document") or data
        markdown = doc_data.get("md_content") or doc_data.get("markdown") or ""
        if not markdown and isinstance(doc_data.get("texts"), list):
            markdown = "\n\n".join(t.get("text", "") for t in doc_data["texts"])

        blocks: list[ExtractedBlock] = []
        page_count = doc_data.get("page_count")
        for item in doc_data.get("texts", []):
            blocks.append(
                ExtractedBlock(
                    text=item.get("text", ""),
                    page=item.get("page") or item.get("prov", [{}])[0].get("page_no"),
                    section_path=item.get("section_path"),
                )
            )

        if not blocks and markdown:
            blocks = [ExtractedBlock(text=markdown)]

        return ExtractedDoc(markdown=markdown, blocks=blocks, page_count=page_count)
