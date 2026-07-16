from __future__ import annotations

import mimetypes
import time
from pathlib import Path

import gradio as gr

from app.api_client import DocumentIndexClient, DocumentIndexError


def _err(exc: Exception) -> str:
    return f"Error: {exc}"


def build_ui(client: DocumentIndexClient) -> gr.Blocks:
    def upload_file(file_path: str | None) -> tuple[str, str]:
        if not file_path:
            return "No file selected.", ""
        path = Path(file_path)
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            result = client.ingest(path.name, path.read_bytes(), mime_type=mime_type)
            return result.document_id, result.status
        except DocumentIndexError as exc:
            return _err(exc), ""

    def poll_status(document_id: str) -> str:
        if not document_id or document_id.startswith("Error"):
            return "Enter a valid document ID from upload."
        try:
            detail = client.get_document(document_id.strip())
            lines = [
                f"**{detail.name}**",
                f"Status: `{detail.status}`",
                f"Pages: {detail.page_count}",
                f"Chunks: {detail.chunk_count}",
            ]
            if detail.error:
                lines.append(f"Error: {detail.error}")
            return "\n\n".join(lines)
        except DocumentIndexError as exc:
            return _err(exc)

    def wait_for_indexed(document_id: str, max_wait: int = 120) -> str:
        if not document_id or document_id.startswith("Error"):
            return "Enter a valid document ID first."
        deadline = time.time() + max_wait
        last = ""
        while time.time() < deadline:
            try:
                detail = client.get_document(document_id.strip())
                last = poll_status(document_id)
                if detail.status in ("INDEXED", "FAILED"):
                    return last
            except DocumentIndexError as exc:
                return _err(exc)
            time.sleep(2)
        return last + "\n\n(Timed out waiting for INDEXED/FAILED.)"

    def refresh_documents() -> list[list]:
        try:
            rows = client.list_documents()
            return [
                [r.document_id, r.name, r.status, r.page_count or "", r.chunk_count]
                for r in rows
            ]
        except DocumentIndexError:
            return []

    def document_detail(document_id: str) -> str:
        return poll_status(document_id)

    def delete_doc(document_id: str) -> tuple[str, list[list]]:
        if not document_id or document_id.startswith("Error"):
            return "Enter a document ID to delete.", refresh_documents()
        try:
            client.delete_document(document_id.strip())
            return f"Deleted `{document_id.strip()}`.", refresh_documents()
        except DocumentIndexError as exc:
            return _err(exc), refresh_documents()

    def run_search(query: str, top_k: int) -> tuple[list[list], str]:
        if not query.strip():
            return [], "Enter a search query."
        try:
            result = client.search(query.strip(), top_k=int(top_k))
            rows = [
                [
                    h.chunk_id,
                    h.document_name,
                    h.page if h.page is not None else "",
                    round(h.score, 3),
                    h.text[:200] + ("…" if len(h.text) > 200 else ""),
                ]
                for h in result.hits
            ]
            return rows, f"Found {result.total} hit(s)."
        except DocumentIndexError as exc:
            return [], _err(exc)

    def show_chunk(chunk_id: str) -> str:
        if not chunk_id.strip():
            return "Select a chunk ID from search results."
        try:
            chunk = client.get_chunk(chunk_id.strip())
            parts = [
                f"### {chunk.document_name}",
                f"Chunk `{chunk.chunk_id}` · page {chunk.page or '?'}",
            ]
            if chunk.context_before:
                parts.append(f"**Before:**\n{chunk.context_before}")
            parts.append(f"**Text:**\n{chunk.text}")
            if chunk.context_after:
                parts.append(f"**After:**\n{chunk.context_after}")
            return "\n\n".join(parts)
        except DocumentIndexError as exc:
            return _err(exc)

    backend_ok = "Connected" if client.health() else "Cannot reach document-index"

    with gr.Blocks(title="Document Console") as demo:
        gr.Markdown(f"# Document Console\nUpload and explore indexed files via REST API. Backend: **{backend_ok}**")

        with gr.Tabs():
            with gr.Tab("Upload"):
                upload_file_input = gr.File(label="Document", file_types=[".pdf", ".docx", ".pptx", ".txt"])
                upload_btn = gr.Button("Upload & ingest", variant="primary")
                doc_id_out = gr.Textbox(label="Document ID", interactive=False)
                status_out = gr.Textbox(label="Initial status", interactive=False)
                detail_md = gr.Markdown(label="Status detail")
                with gr.Row():
                    poll_btn = gr.Button("Refresh status")
                    wait_btn = gr.Button("Wait until indexed")

                upload_btn.click(upload_file, upload_file_input, [doc_id_out, status_out])
                poll_btn.click(poll_status, doc_id_out, detail_md)
                wait_btn.click(wait_for_indexed, doc_id_out, detail_md)

            with gr.Tab("Documents"):
                refresh_btn = gr.Button("Refresh list")
                docs_table = gr.Dataframe(
                    headers=["document_id", "name", "status", "pages", "chunks"],
                    label="Indexed documents",
                    interactive=False,
                )
                selected_id = gr.Textbox(label="Document ID")
                with gr.Row():
                    detail_btn = gr.Button("Show detail")
                    delete_btn = gr.Button("Delete", variant="stop")
                doc_action_msg = gr.Markdown()

                refresh_btn.click(refresh_documents, outputs=docs_table)
                detail_btn.click(document_detail, selected_id, doc_action_msg)
                delete_btn.click(delete_doc, selected_id, [doc_action_msg, docs_table])

            with gr.Tab("Search"):
                search_query = gr.Textbox(label="Query", placeholder="Semantic search over indexed chunks")
                top_k = gr.Slider(1, 20, value=8, step=1, label="Top K")
                search_btn = gr.Button("Search", variant="primary")
                search_msg = gr.Markdown()
                search_table = gr.Dataframe(
                    headers=["chunk_id", "document", "page", "score", "snippet"],
                    label="Results",
                    interactive=False,
                )
                chunk_id_input = gr.Textbox(label="Chunk ID (from results)")
                chunk_btn = gr.Button("Show chunk")
                chunk_md = gr.Markdown()

                search_btn.click(run_search, [search_query, top_k], [search_table, search_msg])
                chunk_btn.click(show_chunk, chunk_id_input, chunk_md)

        demo.load(refresh_documents, outputs=docs_table)

    return demo
