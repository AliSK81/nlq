# NLQ-over-Files Platform

Open-source, locally deployed **Natural Language Query system over uploaded files**. Upload documents, index them with pluggable extractors, and ask questions via Open WebUI with grounded answers and citations.

## Quick Start

1. Copy environment template and configure your LLM provider:

```bash
cp .env.example .env
# Edit .env — set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
```

2. Start the stack:

```bash
docker compose up -d
```

3. Verify services:

```bash
curl http://localhost:8080/health   # Document Index
curl http://localhost:8000/health   # Query Agent
```

4. Open **Open WebUI** at [http://localhost:3000](http://localhost:3000)

5. Attach a document in chat or ingest for persistent indexing:

```bash
curl -X POST http://localhost:8080/ingest -F "file=@your-document.pdf"
```

6. Poll until indexed:

```bash
curl http://localhost:8080/documents/{document_id}
```

7. In Open WebUI, select model **file-qa-agent** and ask a question about your document.

## Architecture

| Service | Port | Role |
|---------|------|------|
| Open WebUI | 3000 | Chat UI |
| Query Agent | 8000 | NLQ conversation, OpenAI-compat API |
| Document Index | 8080 | Ingestion, search, document registry |
| docling-serve | 5001 | Document extraction |
| Qdrant | 6333 | Vector search |
| PostgreSQL | 5433 | Document metadata |

## Project layout

```
document-index/   IngestDocument, SearchDocuments, ListDocuments, FetchChunk
query-agent/      ClassifyIntent, BuildAnswer, grounded Q&A graph
infra/            Postgres schema
```

Each service follows the same layers: `domain/`, `usecases/`, `adapters/`, `delivery/`.

## Optional Profiles

```bash
EXTRACTOR=tika docker compose --profile tika up -d
docker compose --profile obs up -d
```

## REST API (Document Index)

- `POST /ingest` — upload file (returns 202)
- `GET /documents` — list documents
- `GET /documents/{id}` — document status
- `DELETE /documents/{id}` — remove document
- `POST /tools` — JSON-RPC document search tools
- `POST /ask` — persisted Q&A (Query Agent)

## Document search tools

JSON-RPC at `POST /tools`:

- `search_documents` — semantic search over chunks
- `list_documents` — list indexed files
- `fetch_chunk` — get chunk with neighbor context

## Development

```bash
cd document-index && pip install -e ".[dev]" && pytest
cd query-agent && pip install -e ".[dev]" && pytest
```

## Configuration

See [`.env.example`](.env.example). Key variables:

- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` — OpenAI-compatible provider
- `DOCUMENT_INDEX_URL` — document index service URL
- `EXTRACTOR` — `docling` (default) or `tika`
- `EMBEDDING_MODEL`, `EMBEDDING_DIM` — embedding model
- `AGENT_TOP_K`, `AGENT_MIN_SCORE`, `AGENT_MAX_REFINES` — retrieval tuning

## License

Open source — see IMPLEMENTATION_PLAN.md for full design reference.
