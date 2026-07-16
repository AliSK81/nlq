# NLQ-over-Files Platform — MVP Implementation Reference

> **Purpose.** This is the single source of truth for building an open-source, locally-deployed **Natural-Language-Query system over uploaded files**. A user uploads documents; content is extracted by pluggable open-source extractors; an LLM-powered agent answers natural-language questions over the extracted content using **MCP tools**. A Cursor agent will implement the system **phase by phase** from this document.
>
> **How to use this doc.** Implement phases in order (0 → 5). Each phase has explicit deliverables, file paths, contracts, and **acceptance criteria**. Do not start a phase until the previous phase's acceptance criteria pass. Everything is open source and runs via a single `docker compose up`.

---

## 0. TL;DR — What we are building

Three services we write + off-the-shelf open-source infrastructure, wired by Docker Compose:

1. **Web UI** — [Open WebUI](https://github.com/open-webui/open-webui) (unmodified). Talks to **query-agent** via the OpenAI-compatible API.
2. **Query Agent** (`query-agent/`) — Python, **FastAPI + LangGraph + LangChain**. Exposes OpenAI-compatible `/v1/chat/completions`. Deterministic graph: classify → retrieve (via document-index **REST**) → generate grounded answer → (bounded refine loop).
3. **Document Index** (`document-index/`) — Python, **FastAPI**. Owns ingestion (upload → extract → chunk → embed → index) and exposes REST search plus optional JSON-RPC `POST /tools`. Talks to Docling/Tika, Qdrant, and Postgres.

Infrastructure (all OSS containers):

| Concern | Choice | Why (2026 research) |
|---|---|---|
| Content extraction | **Docling** via `docling-serve` (pluggable; Tika alternative) | MIT, best-in-class table (97.9%) + layout, OCR, PDF/DOCX/PPTX/XLSX/HTML/img/audio, LangChain + MCP integrations, local execution |
| Vector search | **Qdrant** | Rust, single Docker command, native payload pre-filtering, on-disk + quantization, production-ready hybrid search |
| Embeddings | **FastEmbed** (ONNX, CPU) — multilingual model | No torch → light images; multilingual (handles Persian & English) |
| Relational/metadata | **PostgreSQL 17** | Document registry, ingestion jobs, optional sessions/history |
| Object storage | Local Docker volume (MinIO optional) | Minimal; MinIO is a drop-in extension |
| Chat UI | **Open WebUI** | Polished, RAG-first, OpenAI-compatible, one-command |
| LLM | **User-configured OpenAI-compatible endpoint** | Provider-agnostic; only chat model needed (embeddings are local) |
| LLM tracing (opt) | **Langfuse** | OSS, LangChain callback |
| HTTP tracing (opt) | **OpenTelemetry → Jaeger** | Spans across FastAPI + httpx (MCP calls) |

**Design principle carried from prior design work:** keep business rules independent of frameworks. LangGraph, Qdrant, Docling, Postgres, and the LLM are **details behind ports/adapters**. The graph is a *delivery mechanism*; classification/grounding/retry **policy** lives in framework-free use-case code so it is unit-testable without any container running.

---

## 1. Scope

### 1.1 In scope (MVP)
- Upload common file formats: **PDF, DOCX, PPTX, XLSX, HTML, TXT/MD, images (PNG/JPG/TIFF via OCR)**.
- Asynchronous ingestion with visible status (`UPLOADED → EXTRACTING → CHUNKING → EMBEDDING → INDEXED | FAILED`).
- Natural-language Q&A over indexed content, **with citations** (file name + page/section).
- Chat through Open WebUI using the user's configured OpenAI-compatible model.
- Single deterministic agent (`file_qa`) with 4-way intent classification (chitchat / intro_capabilities / file_query / off_topic), grounded answering, and a bounded retrieval-refinement loop.
- Everything local via `docker compose up`.

### 1.2 Non-goals (explicit deferrals, see §14)
- Multi-tenant auth/RBAC (seam kept; single corpus in MVP).
- SQL/warehouse querying (this is file content Q&A, not the reference's Trino path).
- Streaming token output (fake SSE single-chunk is acceptable for MVP).
- Horizontal scaling / K8s.
- Reranking, GraphRAG, agentic multi-hop tool planning (Phase 5 extensions).

---

## 2. Architecture

```mermaid
flowchart TB
    subgraph client [Client]
      UI[Open WebUI :3000]
      UP[Upload: platform REST or curl]
    end

    subgraph orch [Agent Orchestrator :8000]
      OAI[POST /v1/chat/completions]
      LG[LangGraph: classify to retrieve to answer]
      MCPC[MCP client httpx]
    end

    subgraph plat [MCP File Platform :8080]
      REST[POST /ingest, GET /documents]
      MCP[POST /mcp JSON-RPC 2.0]
      ING[Ingestion pipeline]
      EMB[FastEmbed embedder]
    end

    subgraph infra [Infrastructure]
      DS[docling-serve :5001 extractor]
      QD[(Qdrant :6333)]
      PG[(PostgreSQL :5432)]
      OBJ[[uploads volume]]
    end

    UI --> OAI --> LG --> MCPC --> MCP
    UP --> REST
    REST --> ING --> DS
    ING --> OBJ
    ING --> EMB --> QD
    ING --> PG
    MCP --> QD
    MCP --> PG
    LG -->|answer + citations| OAI
```

### 2.1 Port map

| Service | Container | Port | Protocol |
|---|---|---|---|
| Open WebUI | `open-webui` | 3000 | HTTP |
| Orchestrator | `orchestrator` | 8000 | HTTP (OpenAI-compat) |
| MCP Platform | `mcp-platform` | 8080 | HTTP (REST + JSON-RPC `/mcp`) |
| Extractor | `docling-serve` | 5001 | HTTP |
| Qdrant | `qdrant` | 6333 (REST/gRPC 6334) | HTTP/gRPC |
| PostgreSQL | `postgres` | 5432 | TCP |
| Langfuse (opt) | `langfuse` | 3001 | HTTP |
| Jaeger (opt) | `jaeger` | 16686 / 4317 | HTTP / OTLP |

### 2.2 Two end-to-end flows

**A. Ingestion (async).**

```mermaid
sequenceDiagram
    participant U as User
    participant P as MCP Platform REST
    participant W as Ingestion Worker
    participant D as docling-serve
    participant E as FastEmbed
    participant Q as Qdrant
    participant G as Postgres

    U->>P: POST /ingest (multipart file)
    P->>G: insert document (status=UPLOADED)
    P->>P: save bytes to uploads volume
    P-->>U: 202 {document_id, status}
    W->>G: claim job (status=EXTRACTING)
    W->>D: POST /v1alpha/convert (file)
    D-->>W: DoclingDocument (markdown + structure)
    W->>W: chunk (HybridChunker) status=CHUNKING
    W->>E: embed chunks status=EMBEDDING
    E-->>W: vectors
    W->>Q: upsert points (vector + payload)
    W->>G: insert chunks, status=INDEXED
```

**B. Query (sync, OpenAI-compatible).**

```mermaid
sequenceDiagram
    participant UI as Open WebUI
    participant O as Orchestrator
    participant L as LLM (OpenAI-compat)
    participant M as MCP Platform
    participant Q as Qdrant

    UI->>O: POST /v1/chat/completions {messages}
    O->>L: classify intent (structured)
    alt intent=file_query
      O->>M: tools/call search_documents(query, top_k)
      M->>Q: vector search (+payload filter)
      Q-->>M: hits
      M-->>O: chunks + citations
      O->>L: answer using ONLY retrieved context
      L-->>O: grounded answer
      opt no hits and retries left
        O->>L: reformulate query -> retry search
      end
    else chitchat/intro/off_topic
      O->>L: short canned/guided reply
    end
    O-->>UI: {choices:[{message.content, reasoning_content}]}
```

---

## 3. Repository layout (monorepo, screaming architecture)

```
nlq-file-platform/
├── docker-compose.yml
├── .env.example
├── README.md
├── IMPLEMENTATION_PLAN.md            # this file
│
├── mcp-platform/                     # Service 1: ingestion + MCP retrieval tools
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── domain/                   # ENTITIES (no framework imports)
│   │   │   ├── document.py           # Document, DocumentId, IngestionStatus
│   │   │   ├── chunk.py              # Chunk, Citation
│   │   │   └── errors.py
│   │   ├── usecases/                 # INTERACTORS (application policy)
│   │   │   ├── ingest_document.py
│   │   │   ├── search_documents.py
│   │   │   ├── list_documents.py
│   │   │   └── ports.py              # Extractor, Chunker, Embedder, VectorIndex, DocumentRepo (Protocols)
│   │   ├── adapters/                 # implement ports over concrete tech
│   │   │   ├── extractors/
│   │   │   │   ├── docling_extractor.py   # default (docling-serve HTTP)
│   │   │   │   └── tika_extractor.py      # alternative (Tika server)
│   │   │   ├── chunking/hybrid_chunker.py
│   │   │   ├── embedding/fastembed_embedder.py
│   │   │   ├── vector/qdrant_index.py
│   │   │   └── repo/postgres_document_repo.py
│   │   ├── delivery/                 # FRAMEWORKS & DRIVERS
│   │   │   ├── rest.py               # POST /ingest, GET /documents, GET /documents/{id}
│   │   │   ├── mcp_server.py         # POST /mcp JSON-RPC + tool dispatch (+SSE)
│   │   │   └── worker.py             # background ingestion worker
│   │   ├── config.py                 # env settings
│   │   └── main.py                   # composition root (wires adapters -> usecases)
│   └── tests/                        # unit (fakes) + contract tests
│
├── orchestrator/                     # Service 2: LangGraph NLQ agent
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── domain/
│   │   │   ├── state.py              # AgentState TypedDict
│   │   │   └── intents.py            # Intent enum, ClassificationOutput, AnswerOutput
│   │   ├── usecases/                 # framework-free policy
│   │   │   ├── classify.py           # rule fallback + structured-output contract
│   │   │   ├── build_answer.py       # grounding rules, citation assembly
│   │   │   └── ports.py              # LlmPort, RetrievalPort
│   │   ├── graph/                    # LangGraph = delivery detail
│   │   │   ├── nodes.py              # thin nodes call usecases
│   │   │   ├── template.py           # nodes[] + edges[] + conditional routes
│   │   │   └── builder.py            # StateGraph.compile()
│   │   ├── adapters/
│   │   │   ├── llm_langchain.py      # LangChain ChatOpenAI (OpenAI-compat) implements LlmPort
│   │   │   └── mcp_retrieval.py      # MCP client implements RetrievalPort
│   │   ├── prompts/                  # versioned prompt files
│   │   │   ├── classification.py
│   │   │   ├── answer_system.py
│   │   │   ├── answer_user.py
│   │   │   └── chitchat.py
│   │   ├── delivery/
│   │   │   └── openai_compat.py      # POST /v1/chat/completions, GET /v1/models, GET /health
│   │   ├── config.py
│   │   └── main.py                   # composition root + graph bootstrap
│   └── tests/
│
└── infra/
    └── postgres/init.sql             # schema DDL
```

Package names scream the business (`ingest_document`, `search_documents`, `build_answer`), not the frameworks. FastAPI/LangGraph/Qdrant/Docling all live in `adapters/` or `delivery/`.

---

## 4. Data model

### 4.1 PostgreSQL DDL (`infra/postgres/init.sql`)

```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY,
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    name            TEXT NOT NULL,
    mime_type       TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    size_bytes      BIGINT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'UPLOADED',   -- UPLOADED|EXTRACTING|CHUNKING|EMBEDDING|INDEXED|FAILED
    error           TEXT,
    extractor       TEXT,                                -- 'docling' | 'tika'
    page_count      INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    indexed_at      TIMESTAMPTZ,
    UNIQUE (tenant_id, content_hash)
);

CREATE TABLE chunks (
    id              UUID PRIMARY KEY,
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    ordinal         INT NOT NULL,
    text            TEXT NOT NULL,
    section_path    TEXT,               -- "Doc > Section > Subsection"
    page            INT,
    token_count     INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_chunks_document ON chunks(document_id);

CREATE TABLE ingestion_jobs (
    id              UUID PRIMARY KEY,
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    stage           TEXT NOT NULL DEFAULT 'PENDING',
    attempts        INT NOT NULL DEFAULT 0,
    last_error      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_jobs_stage ON ingestion_jobs(stage);

-- Optional (Phase 4): conversation history
CREATE TABLE sessions (
    id UUID PRIMARY KEY, username TEXT, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE messages (
    id UUID PRIMARY KEY, session_id UUID REFERENCES sessions(id),
    sender TEXT, text TEXT, intent TEXT, citations JSONB,
    tokens_used INT, created_at TIMESTAMPTZ DEFAULT now()
);
```

### 4.2 Qdrant collection

- Collection name: `document_chunks`.
- Vector: size = embedding dim (see §5.1), distance = `Cosine`.
- Point `id`: chunk UUID (same as `chunks.id`).
- Payload (indexed fields in **bold** for pre-filtering):
  - **`tenant_id`** (keyword), **`document_id`** (keyword), `document_name` (keyword), `ordinal` (int), `page` (int), `section_path` (text), `text` (text).
- Create payload indexes on `tenant_id` and `document_id` so per-file / per-tenant filters use pre-filtering.

**Source of truth rule:** Postgres owns document/chunk metadata; Qdrant owns vectors + a denormalized payload copy for retrieval. On delete, cascade Postgres then delete Qdrant points by `document_id` filter.

---

## 5. Pluggable extraction & embeddings

### 5.1 Embeddings (FastEmbed)
- Library: `fastembed` (ONNX, CPU-only, no torch).
- **Default model:** `intfloat/multilingual-e5-small` (384-dim) — light, multilingual (Persian + English). Prefix rule: embed passages as `"passage: {text}"` and queries as `"query: {text}"` (e5 convention).
- **Quality option (Phase 5 / hybrid):** `BAAI/bge-m3` (1024-dim, dense+sparse+multi-vector) enabling native hybrid search in Qdrant.
- Embedding dim is a single config value (`EMBEDDING_DIM`) consumed by both the Qdrant collection creator and the embedder. Changing the model = change model id + dim + re-index. Never hardcode 384 in two places.

### 5.2 Extractor port (the pluggable seam)

```python
# mcp-platform/app/usecases/ports.py
class Extractor(Protocol):
    name: str
    def supports(self, mime_type: str) -> bool: ...
    def extract(self, blob: bytes, filename: str, mime_type: str) -> ExtractedDoc:
        """Returns normalized markdown + ordered blocks with page/section metadata."""
```

- **`DoclingExtractor` (default):** POSTs the file to `docling-serve` (`POST /v1alpha/convert/file`), receives `DoclingDocument`; export to markdown + iterate items for `page`/`heading` metadata. Handles PDF/DOCX/PPTX/XLSX/HTML/images(OCR)/audio.
- **`TikaExtractor` (alternative):** POSTs to Tika server `PUT /tika` (text) + `/meta`. Broader format count, weaker layout/tables. Selected by env `EXTRACTOR=tika`.
- Adding an extractor = new adapter implementing `Extractor` + registry entry in the composition root. No use-case changes.

### 5.3 Chunking
- `HybridChunker` from `docling` (or a token-window fallback): layout-aware, token-bounded (target ≈ 512 tokens, overlap ≈ 64), keeps tables intact, attaches `section_path` + `page` to each chunk. Token counts via `tiktoken`.

---

## 6. MCP contract (the interop boundary)

The orchestrator calls the platform at `{MCP_BASE_URL}/mcp`. **Transport identical to the reference** so tooling stays compatible.

### 6.1 Transport
| Aspect | Value |
|---|---|
| Method | `POST /mcp` |
| Format | JSON-RPC 2.0 |
| Inbound headers | `Content-Type: application/json`, `Accept: application/json, text/event-stream`, `X-Api-Version: 1` |
| Auth pass-through (MVP optional) | `Cookie`, `Authorization`, `X-Auth-Token` forwarded verbatim; platform derives `tenant_id` (MVP: always `default`) |
| Response | Plain JSON **or** SSE (`text/event-stream` `data:` lines) |
| Result extraction | `result.content[]` where `type == "text"`; the `text` is a JSON string the client parses |
| Errors | JSON-RPC `error` object **or** `result.isError: true` |

Envelope:

```json
{ "jsonrpc": "2.0", "id": 1, "method": "tools/call",
  "params": { "name": "search_documents", "arguments": { "query": "...", "top_k": 8 } } }
```

Also implement `method: "tools/list"` returning the three tool schemas (used for discovery / tests).

### 6.2 Tool: `search_documents`
Purpose: semantic (Phase 5: hybrid) search over indexed chunks.

Input:
```json
{ "query": "string (required)",
  "top_k": 8,
  "min_score": 0.3,
  "document_ids": ["uuid", "..."],   // optional filter
  "tenant_id": "default" }            // optional; server overrides from auth
```

Output (inside `result.content[0].text` as JSON):
```json
{ "hits": [
    { "chunk_id": "uuid", "document_id": "uuid", "document_name": "report.pdf",
      "page": 4, "section_path": "Results > Q3", "score": 0.82,
      "text": "..." } ],
  "total": 8 }
```
Empty `hits` → orchestrator treats as "not found" (drives refine loop / abstain).

### 6.3 Tool: `list_documents`
Input: `{ "status": "INDEXED", "limit": 50, "tenant_id": "default" }`
Output:
```json
{ "documents": [
   { "document_id": "uuid", "name": "report.pdf", "mime_type": "application/pdf",
     "status": "INDEXED", "page_count": 12, "chunk_count": 40 } ],
  "total": 1 }
```

### 6.4 Tool: `fetch_chunk`
Purpose: pull full text + neighbors for precise grounding / citation expansion.
Input: `{ "chunk_id": "uuid", "neighbors": 1 }`
Output:
```json
{ "chunk_id": "uuid", "document_id": "uuid", "document_name": "report.pdf",
  "page": 4, "section_path": "Results > Q3",
  "text": "full chunk text",
  "context_before": "prev chunk text|null", "context_after": "next chunk text|null" }
```

### 6.5 Platform REST (non-MCP, for ingestion)
| Route | Method | Body / Params | Response |
|---|---|---|---|
| `/ingest` | POST (multipart) | `file`, optional `tenant_id` | `202 {document_id, status}` |
| `/documents` | GET | `?status=&limit=` | `[{document_id,name,status,...}]` |
| `/documents/{id}` | GET | — | `{document_id, status, error, chunk_count, ...}` |
| `/documents/{id}` | DELETE | — | `204` (cascade PG + Qdrant) |
| `/health` | GET | — | `{status:"ok"}` |

---

## 7. Agent orchestrator design

### 7.1 Shared graph state (`app/domain/state.py`)

```python
class AgentState(TypedDict, total=False):
    # inputs
    question: str
    memory_context: str                  # last N turns "user: ...\nassistant: ..."
    mcp_auth: dict[str, str | None]       # {cookie, authorization, x_auth_token}
    config: dict                          # {top_k, min_score, max_refines}
    # classification
    intent: str | None                    # chitchat|intro_capabilities|file_query|off_topic
    intent_message: str | None
    # retrieval
    hits: list[dict] | None               # from search_documents
    refine_count: int
    should_refine: str | None             # "refine" | "done"
    # answer
    answer_text: str | None
    citations: list[dict] | None
    grounded: bool
    # terminal + telemetry
    success: bool
    error: str | None
    steps: Annotated[list[dict], add]     # [{node, success, duration_ms}]
    total_tokens_used: Annotated[int, add_int]   # reducer sums across nodes (fixes ref gap #4)
```

### 7.2 Graph template (`app/graph/template.py`)

```
nodes = [ classify, chitchat, retrieve, generate_answer ]

edges:
  START -> classify
  classify --intent-->
      file_query        -> retrieve
      chitchat|intro_capabilities|off_topic -> chitchat -> END
  retrieve --route-->
      hits_found        -> generate_answer -> END
      empty & refines_left -> retrieve (with reformulated query)   # bounded loop
      empty & no_refines   -> generate_answer (abstain)  -> END
```

Conditional routes read `intent` and `should_refine`. **Default/safe route is listed first** in each mapping (terminal/abstain path), fixing reference gap #1 (never silently proceed on empty retrieval — an explicit abstain edge exists).

### 7.3 Nodes (thin) → use cases (policy)

| Node | Reads | Writes | Policy lives in |
|---|---|---|---|
| `classify` | `question` | `intent`, `intent_message`, tokens | `usecases/classify.py` (LLM structured output + rule fallback: greeting→chitchat; `looks_like_file_query()`→file_query; bot-reflexive→intro; else off_topic) |
| `chitchat` | `intent`, `question` | `answer_text`, `success` | static strings + optional LLM with `list_documents` context for intro/off_topic |
| `retrieve` | `question`, `config`, `refine_count` | `hits`, `should_refine`, `refine_count` | MCP `search_documents`; if empty and `refine_count < max_refines` → reformulate (LLM) and set `should_refine="refine"` |
| `generate_answer` | `question`, `hits`, `memory_context` | `answer_text`, `citations`, `grounded`, tokens | `usecases/build_answer.py`: prompt LLM to answer **only** from `hits`; if `hits` empty → deterministic abstain message; assemble citations from hit metadata |

### 7.4 Prompts (versioned files, `app/prompts/`)
- **`answer_system.py`** — rules: answer only from provided context; if insufficient, say so (in the user's language); always cite `[document_name p.N]`; never invent facts; be concise; match the question's language (Persian or English).
- **`answer_user.py`** — assembles: retrieved context blocks (with `document_name`, `page`, `section_path`), optional `memory_context`, then the user question and an output contract (JSON: `{answer, citations[], confidence}`).
- **`classification.py`** — 4-way classifier, JSON-only output `{intent, message_text}` (message_text only for chitchat).
- Log a prompt version/hash per run for evaluation (reference §4.5).

### 7.5 OpenAI-compatible API (`app/delivery/openai_compat.py`)
- `GET /health` → `{status:"ok"}`.
- `GET /v1/models` → `[{id:"file-qa-agent"}, {id:"file-qa"}]`.
- `POST /v1/chat/completions`:
  - Take last user message as `question`; build `memory_context` from prior messages (window `OPENAI_COMPAT_MEMORY_WINDOW`, default 5).
  - Forward inbound auth headers into `mcp_auth`.
  - Run graph via `AgentFactory.run("file_qa", **state)`.
  - Response: `choices[0].message.content` = final answer (markdown + citations); `reasoning_content` = intent + retrieval summary + timing. `finish_reason:"stop"`. `usage` filled from `total_tokens_used`.
  - `stream=true` → single SSE chunk + `[DONE]` (fake streaming acceptable for MVP).
  - No DB write on this path (matches reference; history is Phase 4 + only on REST paths).

---

## 8. Configuration (`.env.example`)

```bash
# ---- LLM (user's OpenAI-compatible provider) ----
LLM_BASE_URL=https://your-provider/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini            # any chat model your provider exposes
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=1500
LLM_TIMEOUT=60

# ---- Orchestrator ----
ORCH_PORT=8000
MCP_BASE_URL=http://mcp-platform:8080
MCP_API_VERSION=1
MCP_TIMEOUT=120
OPENAI_COMPAT_MEMORY_WINDOW=5
AGENT_TOP_K=8
AGENT_MIN_SCORE=0.3
AGENT_MAX_REFINES=1

# ---- MCP Platform ----
PLATFORM_PORT=8080
EXTRACTOR=docling                 # docling | tika
DOCLING_URL=http://docling-serve:5001
TIKA_URL=http://tika:9998
EMBEDDING_MODEL=intfloat/multilingual-e5-small
EMBEDDING_DIM=384
CHUNK_TARGET_TOKENS=512
CHUNK_OVERLAP_TOKENS=64
UPLOAD_DIR=/data/uploads
MAX_UPLOAD_MB=50
INGEST_WORKER_CONCURRENCY=2

# ---- Qdrant ----
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=document_chunks

# ---- Postgres ----
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/nlq
DATABASE_ENABLED=1

# ---- Observability (optional) ----
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=http://langfuse:3000
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_SERVICE_NAME=nlq-orchestrator

# ---- Open WebUI ----
OPENAI_API_BASE_URL=http://orchestrator:8000/v1
OPENAI_API_KEY=local-anything
```

All runtime knobs (`top_k`, `min_score`, `max_refines`) also live in the graph `config` dict so they are per-request overridable. **One key per concept** (fixes reference gap #2 — no divergent `max_rows` values).

---

## 9. Docker Compose

`docker-compose.yml` services (base profile) + optional profiles `obs` (Langfuse+Jaeger) and `tika` (swap extractor).

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333", "6334:6334"]
    volumes: ["qdrant_data:/qdrant/storage"]

  postgres:
    image: postgres:17
    environment:
      POSTGRES_DB: nlq
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s

  docling-serve:
    image: quay.io/docling-project/docling-serve:latest
    ports: ["5001:5001"]
    environment:
      DOCLING_SERVE_ENABLE_UI: "false"

  mcp-platform:
    build: ./mcp-platform
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      qdrant: { condition: service_started }
      docling-serve: { condition: service_started }
    ports: ["8080:8080"]
    volumes: ["uploads:/data/uploads"]

  orchestrator:
    build: ./orchestrator
    env_file: .env
    depends_on:
      mcp-platform: { condition: service_started }
    ports: ["8000:8000"]

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    depends_on:
      orchestrator: { condition: service_started }
    environment:
      OPENAI_API_BASE_URL: http://orchestrator:8000/v1
      OPENAI_API_KEY: local-anything
      WEBUI_AUTH: "false"          # MVP: skip login
    ports: ["3000:8080"]
    volumes: ["openwebui_data:/app/backend/data"]

  # profile: tika  (alternative extractor)
  tika:
    image: apache/tika:latest-full
    ports: ["9998:9998"]
    profiles: ["tika"]

  # profile: obs
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports: ["16686:16686", "4317:4317"]
    profiles: ["obs"]

volumes:
  qdrant_data: {}
  pg_data: {}
  uploads: {}
  openwebui_data: {}
```

`docker compose up -d` → base stack. `docker compose --profile obs up -d` → add tracing. `EXTRACTOR=tika docker compose --profile tika up -d` → swap extractor. (Langfuse needs its own compose include; document separately in Phase 4.)

---

## 10. Phased implementation plan (deterministic)

> Rule: a phase is "done" only when **all** its acceptance criteria pass. Each phase ends green before the next begins.

### Phase 0 — Scaffold & compose skeleton
**Deliverables**
- Monorepo tree from §3 (empty modules with docstrings).
- `pyproject.toml` per service (deps in §16), `Dockerfile` per service.
- `docker-compose.yml` (§9), `.env.example` (§8), `infra/postgres/init.sql` (§4.1), root `README.md`.
- `/health` endpoints returning `{status:"ok"}` for both services.

**Acceptance**
- `docker compose up -d` starts qdrant, postgres, docling-serve, mcp-platform, orchestrator, open-webui with all containers healthy.
- `curl localhost:8080/health` and `curl localhost:8000/health` both return ok.
- Postgres has the schema (verify tables exist).
- Open WebUI loads at `localhost:3000`.

### Phase 1 — MCP File Platform (ingestion + retrieval tools)
**Deliverables**
- Domain entities (`Document`, `Chunk`, `IngestionStatus`) with invariants + status transitions.
- Ports (`Extractor`, `Chunker`, `Embedder`, `VectorIndex`, `DocumentRepo`).
- Adapters: `DoclingExtractor`, `HybridChunker`, `FastembedEmbedder`, `QdrantIndex`, `PostgresDocumentRepo`.
- Use cases: `ingest_document`, `search_documents`, `list_documents`, `fetch_chunk`.
- Delivery: REST (`/ingest`, `/documents`, `/documents/{id}`, DELETE), background `worker`, JSON-RPC `/mcp` with the 3 tools + `tools/list` + SSE support.
- Composition root wiring adapters → use cases (extractor selected by `EXTRACTOR` env).
- Qdrant collection auto-created on startup using `EMBEDDING_DIM`.

**Acceptance**
- Upload a sample PDF via `POST /ingest` → poll `GET /documents/{id}` → reaches `INDEXED`; chunks present in Postgres and points in Qdrant (counts match).
- JSON-RPC `tools/call search_documents` for a query answerable by the PDF returns non-empty `hits` with correct `document_name` + `page` + `score`, wrapped in `result.content[0].text` JSON.
- `list_documents` and `fetch_chunk` return correct shapes (§6).
- DELETE removes rows and Qdrant points.
- Contract test: a stored fixture of expected JSON-RPC responses passes (this is what the orchestrator parser depends on).
- Unit tests for use cases run with **in-memory fakes** (no Qdrant/PG/Docling needed), green.

### Phase 2 — Agent orchestrator (LangGraph)
**Deliverables**
- `AgentState`, `Intent`/`ClassificationOutput`/`AnswerOutput` models.
- Use cases `classify` (LLM + rule fallback) and `build_answer` (grounding + citations + abstain).
- Ports `LlmPort`, `RetrievalPort`; adapters `llm_langchain` (LangChain `ChatOpenAI` → OpenAI-compat), `mcp_retrieval` (MCP client + tolerant response parser per §6).
- Graph: `nodes.py`, `template.py`, `builder.py`; `AgentFactory.run(...)`.
- Prompt files (§7.4).
- Composition root + graph bootstrap.

**Acceptance**
- Unit tests: each node/use case runs with **fake LlmPort + fake RetrievalPort** (no LLM, no MCP). Cases: `file_query` with hits → grounded answer + citations; empty hits + refines exhausted → abstain; chitchat/intro/off_topic routes.
- Integration test: orchestrator against the **real Phase-1 platform** (compose up) with a mocked/stubbed LLM → returns an answer citing the ingested PDF.
- `total_tokens_used` correctly summed across nodes (reducer works).

### Phase 3 — End-to-end via Open WebUI
**Deliverables**
- `/v1/chat/completions`, `/v1/models`, `/health` finalized (§7.5).
- Open WebUI wired to `http://orchestrator:8000/v1`.
- README "quick start": configure `.env` LLM, `docker compose up`, upload a file, ask a question.

**Acceptance**
- From Open WebUI, select the `file-qa-agent` model, ask a question about the uploaded PDF, and receive a grounded answer with citations in the chat.
- Off-topic/greeting messages get appropriate short replies (no hallucinated file content).
- `reasoning_content` shows intent + retrieval summary + timing.

### Phase 4 — Persistence & observability (optional but specified)
**Deliverables**
- Sessions/messages tables active; a REST `/ask` endpoint that persists question + answer + citations + tokens (chat-completions path stays stateless).
- `ConversationHistoryManager.get_memory_context(n)`.
- Langfuse callback wired when keys present (tags: `file-qa`, `openai-compat`).
- OTEL instrumentation for FastAPI + httpx when `OTEL_EXPORTER_OTLP_ENDPOINT` set; Jaeger via `--profile obs`.
- Per-node `steps` telemetry recorded.

**Acceptance**
- With Langfuse keys set, a query produces a trace with per-node spans and token counts.
- With `--profile obs`, HTTP spans (UI→orch→MCP) visible in Jaeger at `localhost:16686`.
- `/ask` persists a row; history reconstructs into subsequent prompts.

### Phase 5 — Hardening & extensions
Pick as needed; each is an **adapter swap or additive node**, no core rewrite:
- **Hybrid search**: switch embedder to `bge-m3`, enable Qdrant sparse+dense fusion in `QdrantIndex`; update `EMBEDDING_DIM` + reindex.
- **Reranker**: add a cross-encoder rerank step in `search_documents` (e.g., `bge-reranker`).
- **Async queue**: replace in-process worker with Redis + `arq`.
- **Object store**: swap local volume adapter for MinIO (S3 API) behind an `ObjectStore` port.
- **Multi-tenant auth**: activate auth pass-through → real `tenant_id` scoping in Qdrant payload filter + Postgres RLS.
- **More extractors**: register additional `Extractor` adapters (e.g., dedicated OCR, ASR) via registry + fallback chain (Docling first, OCR fallback on low text yield).
- **CI**: GitHub Actions running lint + type-check + unit + contract tests with a coverage gate.

---

## 11. Testing strategy (TDD, deterministic)

Because all IO sits behind ports, the valuable logic tests need **no containers**:

- **Entities** (`domain/`): pure unit tests for invariants (status transitions, "grounded ⇒ has citations").
- **Use cases** (`usecases/`): tested with in-memory fakes for every port. Assert on returned response models / written state. Millisecond, deterministic. Target ~100% coverage here.
- **Contract tests**: one shared suite runs against **every** adapter of a port (in-memory + real) — guarantees `QdrantIndex`, `PostgresDocumentRepo`, and the MCP JSON-RPC responses honor the same contract the orchestrator parser expects. This is the interop safety net.
- **Adapters/delivery** (Humble Object): keep them thin (pure translation, no branching) so the untested surface is minimal; cover with a small layer of integration tests against compose containers.
- **E2E smoke** (Phase 3): scripted ingest → ask → assert citation present, run against `docker compose up` with a stub LLM.

Determinism rules: fix `LLM_TEMPERATURE=0.1`; stub the LLM in tests; seed embeddings via a fixed model; assert on structure (intent, hit doc/page, citation presence), not exact LLM prose.

---

## 12. Design decisions & gaps deliberately avoided

Carried from the reference's "known gaps" (§14 there) — fixed here by design:

| Ref gap | Fix in this design |
|---|---|
| Retrieval failure silently proceeds | Explicit abstain edge after `retrieve`; safe route listed first (§7.2) |
| Divergent config defaults (`max_rows` 20 vs 1000) | One key per concept; per-request `config` dict (§8) |
| IDs/filters from LLM only | Filters derived server-side; auth-scoped `tenant_id` never trusted from client (§6.1) |
| `total_tokens_used` not summed | Reducer on state field (§7.1) |
| No tests despite pytest config | TDD-first; contract + unit + E2E gates per phase (§11) |
| Hardcoded timeouts | All timeouts in `.env` (§8) |
| Framework holding logic hostage | LangGraph/Qdrant/Docling/LLM are adapters; policy in `usecases/` (§3) |

---

## 13. Dependencies per service (§16 detail)

**`mcp-platform/pyproject.toml`**
```
fastapi, uvicorn[standard], pydantic>=2, pydantic-settings,
httpx, python-multipart,
sqlalchemy>=2, psycopg[binary],
qdrant-client, fastembed, tiktoken,
docling                      # for HybridChunker + DoclingDocument types
# dev: pytest, pytest-asyncio, pytest-cov, ruff, mypy, respx (httpx mocking)
```

**`orchestrator/pyproject.toml`**
```
fastapi, uvicorn[standard], pydantic>=2, pydantic-settings, httpx,
langchain-core, langchain-openai, langgraph<1.0,
langfuse,                    # optional tracing
opentelemetry-sdk, opentelemetry-instrumentation-fastapi,
opentelemetry-instrumentation-httpx, opentelemetry-exporter-otlp
# dev: pytest, pytest-asyncio, pytest-cov, ruff, mypy, respx
```

Off-the-shelf images: `qdrant/qdrant`, `postgres:17`, `quay.io/docling-project/docling-serve`, `ghcr.io/open-webui/open-webui:main`, optional `apache/tika:latest-full`, `jaegertracing/all-in-one`.

Pin exact versions at implementation time via the package manager; do not invent versions.

---

## 14. Definition of done (MVP)

1. `docker compose up -d` brings up the full base stack healthy.
2. A user uploads a PDF/DOCX/PPTX and it reaches `INDEXED`.
3. In Open WebUI, asking a question about that file returns a **grounded answer with citations** in the file's language (Persian or English).
4. Irrelevant/greeting inputs are handled without hallucinating file content.
5. When the answer isn't in the corpus, the agent **abstains** ("not found in your documents").
6. Unit + contract test suites pass; use-case coverage ~100%.
7. Swapping `EXTRACTOR=tika` (profile) still ingests successfully — proving the extractor is pluggable.

---

## 15. Build order checklist (for the implementing agent)

- [ ] Phase 0: scaffold, compose, health, schema
- [ ] Phase 1: platform entities → ports → adapters → use cases → REST + worker + `/mcp`; ingest a PDF to `INDEXED`; tools return correct shapes; contract + unit tests green
- [ ] Phase 2: orchestrator state → use cases → ports → adapters → graph → factory; node/use-case unit tests green; integration test green
- [ ] Phase 3: OpenAI-compat endpoint final; Open WebUI wired; E2E ask-about-file works
- [ ] Phase 4 (optional): persistence + Langfuse + OTEL/Jaeger
- [ ] Phase 5 (optional): hybrid/rerank/async queue/MinIO/multi-tenant/CI

**Start at Phase 0. Do not skip acceptance gates.**





