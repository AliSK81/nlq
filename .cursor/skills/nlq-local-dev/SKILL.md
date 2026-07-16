---
name: nlq-local-dev
description: Run, test, and rebuild the NLQ docker stack (document-index, query-agent, Open WebUI). Use when starting the dev environment, running pytest, rebuilding services, or verifying health endpoints after code changes.
---

# NLQ local development

## Prerequisites

- Docker Compose
- `.env` from `.env.example` with `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` set

## Start / stop

```bash
docker compose up -d
docker compose ps
docker compose logs -f query-agent    # or document-index, open-webui
docker compose down
```

Health:

```bash
curl -s http://localhost:8080/health
curl -s http://localhost:8000/health
curl -s http://localhost:3000/health
```

## Unit tests (no Docker)

```bash
cd document-index && pip install -e ".[dev]" && pytest
cd query-agent     && pip install -e ".[dev]" && pytest
```

Run tests for the service you changed before rebuilding images.

## Rebuild after Python changes

```bash
docker compose up -d --build query-agent
docker compose up -d --build document-index
```

## Persistent indexing smoke test

```bash
curl -X POST http://localhost:8080/ingest -F "file=@path/to/doc.pdf"
curl -s http://localhost:8080/documents
```

## Open WebUI

- UI: http://localhost:3000
- Select model **file-qa-agent**
- For attachment issues, use skill **nlq-debug-qa**

## Config discovery

Do not hardcode ports or env names — read `docker-compose.yml`, `.env.example`, and `{service}/app/config.py`.
