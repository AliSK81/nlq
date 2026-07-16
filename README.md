# NLQ-over-Files Platform

Open-source, locally deployed **Natural Language Query system over uploaded files**. Upload documents, index them with pluggable extractors, and ask questions via Open WebUI with grounded answers and citations.

## Happy path

1. `cp .env.example .env` and set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.
2. `docker compose up -d --build`
3. Open **Document Console** at [http://localhost:8081](http://localhost:8081) → upload a file → wait until status is `INDEXED`.
4. Open **Open WebUI** at [http://localhost:3000](http://localhost:3000) → select model **file-qa-agent** → ask a question.
5. Inspect `reasoning_content` on the response (intent, hits, grounded) via API or debug tooling.

Or smoke the same path:

```bash
python scripts/compose_smoke.py
```

**Note:** After enabling hybrid search, recreate the Qdrant collection (or wipe the `qdrant_data` volume) so named dense+sparse vectors are created.

## Quick Start (API)

```bash
cp .env.example .env
docker compose up -d
curl http://localhost:8080/health   # Document Index
curl http://localhost:8000/health   # Query Agent
curl -X POST http://localhost:8080/ingest -F "file=@your-document.pdf"
```

## Architecture

| Service | Port | Role |
|---------|------|------|
| Open WebUI | 3000 | Chat UI |
| Document Console | 8081 | Upload, list, search indexed documents (Gradio) |
| Query Agent | 8000 | LangGraph NLQ + OpenAI-compat API |
| Document Index | 8080 | Ingest, hybrid search, document registry |
| docling-serve | 5001 | Document extraction |
| Qdrant | 6333 | Hybrid vector search (dense + BM25 sparse) |
| PostgreSQL | 5433 | Document metadata |

**Retrieval:** Document Index uses **Chonkie** chunking, **FastEmbed** dense + BM25 sparse embeddings, **Qdrant RRF hybrid** search, and an optional FastEmbed cross-encoder **reranker**. Query Agent talks to Document Index over **REST** (`/search`, `/documents`, `/chunks`). JSON-RPC `POST /tools` remains for external agents.

**Out of scope (use a product like Onyx if needed):** GraphRAG, multi-tenant RBAC, MinIO object store, enterprise connectors.

## Project layout

```
document-index/   IngestDocument, SearchDocuments, ListDocuments, FetchChunk
document-console/ Gradio UI — thin client over document-index REST API
query-agent/      ClassifyIntent, BuildAnswer, grounded Q&A graph
evals/            Golden set + DeepEval quality gates
perf/k6/          Load tests (p95 budgets)
infra/            Postgres schema
```

Each Python service follows: `domain/` → `usecases/` (+ `ports.py`) → `adapters/` → `delivery/`.

## Optional Profiles

```bash
EXTRACTOR=tika docker compose --profile tika up -d
docker compose --profile obs up -d   # Jaeger OTEL
```

## REST API (Document Index)

- `POST /ingest` — upload file (returns 202)
- `GET /documents` — list documents
- `GET /documents/{id}` — document status
- `DELETE /documents/{id}` — remove document
- `POST /search` — hybrid semantic search over chunks
- `GET /documents/{id}/chunks` — all chunks for a document
- `GET /chunks/{id}` — chunk text with neighbor context
- `POST /tools` — optional JSON-RPC tools (external agents)

Query Agent: `POST /v1/chat/completions`, `POST /ask`.

## Development & tests

```bash
cd document-index && pip install -e ".[dev]" && pytest -m "not integration"
cd document-console && pip install -e ".[dev]" && pytest
cd query-agent     && pip install -e ".[dev]" && pytest
```

Integration (Docker required):

```bash
cd document-index && pytest tests/test_integration_qdrant.py
```

RAG quality (needs `LLM_API_KEY`):

```bash
pytest evals/test_rag_quality.py
```

Performance (stack must be up):

```bash
k6 run perf/k6/rag_load.js
# local budgets: search p95 < 2s, chat p95 < 15s
# CI: docker-compose.ci.yml (Tika + mock LLM) + K6_PROFILE=ci
```

## Configuration

See [`.env.example`](.env.example). Key variables:

- `LLM_*` — OpenAI-compatible provider
- `HYBRID_SEARCH`, `RERANKER`, `RERANK_CANDIDATE_MULTIPLIER` — retrieval power
- `AGENT_TOP_K`, `AGENT_MIN_SCORE`, `AGENT_MIN_CONFIDENCE` — agent gates
- `EMBEDDING_MODEL`, `EMBEDDING_DIM` — dense model (upgrade path: BGE-M3)
- `LANGFUSE_*` / `OTEL_*` — optional tracing

## License

Open source — see IMPLEMENTATION_PLAN.md for historical design notes (service names there may lag; trust this README and compose).
