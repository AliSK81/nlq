from __future__ import annotations

from app.api_client import DocumentIndexClient
from app.config import settings
from app.ui import build_ui


def main() -> None:
    client = DocumentIndexClient(settings.document_index_url, timeout=settings.request_timeout)
    demo = build_ui(client)
    demo.launch(
        server_name=settings.console_host,
        server_port=settings.console_port,
        show_error=True,
    )


if __name__ == "__main__":
    main()
