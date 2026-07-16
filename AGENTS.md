# Agent guide — NLQ-over-Files

Natural-language Q&A over uploaded documents. Two Python services plus Docker infrastructure; Open WebUI is the chat front-end.

**This file stays useful by describing stable roles and discovery habits — not inventories that go stale.** When details conflict, trust the repo (README, compose, source) over this doc.

---

## Discover current state

| Need | Look here first |
|------|-----------------|
| Ports, service names, env vars | `docker-compose.yml`, `.env.example` |
| Quick start & API surface | `README.md` |
| Layer layout inside a service | `{service}/app/` — expect `domain/`, `usecases/`, `adapters/`, `delivery/` |
| Config keys & defaults | `{service}/app/config.py`, `.env.example` |
| Tests & how to run them | `{service}/tests/`, `{service}/pyproject.toml` |
| Historical / phased design notes | `IMPLEMENTATION_PLAN.md` (may lag renames) |

Explore with search, not memory: `rg`, file tree, and reading `ports.py` / `delivery/` entrypoints beat guessing filenames.

---

## Service responsibilities (stable)

| Service | Role |
|---------|------|
| **document-index** | Ingest files, extract/chunk/embed, store metadata, search |
| **query-agent** | Intent routing, retrieval orchestration, grounded answers, OpenAI-compat API for WebUI |
| **Open WebUI** | Chat UI; attaches files and forwards messages to query-agent |
| **docling-serve** | PDF/document extraction (used by document-index and should be used by WebUI for attachments) |
| **Postgres / Qdrant** | Document registry and vector index |

**Data paths**

1. **Persistent index** — `POST /ingest` on document-index → search via query-agent → document-index client.
2. **Chat attachments** — WebUI injects `<source>…</source>` context into the user message → query-agent `parse_webui_rag` → `prefetched_hits` (no index required).

Both paths can coexist; debug which path a conversation uses before changing retrieval code.

---

## Architecture conventions

Apply to **document-index** and **query-agent**:

1. **domain/** — entities, enums, errors; no I/O.
2. **usecases/** — business workflows; depend on **ports** (interfaces), not concrete adapters.
3. **adapters/** — LLM, DB, HTTP clients, extractors; implement ports.
4. **delivery/** — FastAPI routers, HTTP/OpenAI shapes; thin — delegate to use cases / graph.

**Naming**

- Prefer business terms in domain and use cases (`DocumentIndexClient`, `IngestDocument`), not vendor/protocol names (`Mcp*`, `Orchestrator*`) unless at the adapter boundary.
- New integrations get a new adapter + port method; avoid leaking adapter types into use cases.

**Change discipline**

- Smallest correct diff; match surrounding style.
- Don't add comments that restate code or document "phases."
- Tests: use fakes in `tests/fakes.py`; unit-test use cases and parsing, not full Docker stacks, unless explicitly asked.

---

## Development workflows

**Stack**

```bash
cp .env.example .env   # set LLM_* 
docker compose up -d
curl http://localhost:8080/health
curl http://localhost:8000/health
```

**Unit tests (per service)**

```bash
cd document-index && pip install -e ".[dev]" && pytest
cd query-agent     && pip install -e ".[dev]" && pytest
```

**Rebuild one service after code changes**

```bash
docker compose up -d --build query-agent
# or document-index
```

**Smoke query-agent**

```bash
curl -s http://localhost:8000/v1/models
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"file-qa-agent","messages":[{"role":"user","content":"hello"}],"stream":false}'
```

Check `reasoning_content` in the response for intent, hit count, and grounded flag.

---

## Debugging Q&A (checklist)

Work top-down; stop when the layer is wrong.

1. **WebUI** — Did attachment extraction succeed? (Admin/settings: docling URL must reach `docling-serve` on the compose network.) Re-attach files after extraction config changes.
2. **Message shape** — Does the payload contain `<source …>text</source>` tags? Empty tags → no usable `prefetched_hits`.
3. **query-agent** — `reasoning_content`: `hits=0` vs `hits≥1`, `grounded=True/False`. Abstain vs LLM “not in documents” vs hard error differ.
4. **document-index** — `GET /documents` empty? Chat-only attachments won't help indexed search until ingest.
5. **LLM gateway** — Empty model response → JSON parse errors in query-agent; retry or reduce context — don't assume RAG logic is broken first.

Use project skill **nlq-debug-qa** (`.cursor/skills/nlq-debug-qa/`) for step-by-step diagnosis.

---

## Cursor resources in this repo

| Resource | Purpose |
|----------|---------|
| `.cursor/rules/` | Short, scoped coding conventions |
| `.cursor/skills/` | Workflows: local dev, Q&A debugging |

Rules and skills intentionally duplicate **process**, not **file lists**.

---

## Out of scope for agents unless asked

- Committing, pushing, or wiping Docker volumes
- Editing `.env` secrets or committing credentials
- Large refactors or renames without explicit request
- Updating `IMPLEMENTATION_PLAN.md` for every small change
