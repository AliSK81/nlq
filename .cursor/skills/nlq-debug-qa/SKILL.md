---
name: nlq-debug-qa
description: Diagnose failed or empty file Q&A in NLQ (Open WebUI attachments, prefetched_hits, document-index search, LLM errors). Use when answers abstain, show JSON/500 errors, wrong document used, or "Retrieved N sources" but no useful answer.
---

# Debug NLQ Q&A

## 1. Classify the failure

| Symptom | Likely layer |
|---------|----------------|
| "could not find relevant information" + `hits=0` | No context reached query-agent |
| "could not find … in the documents" + `hits≥1` | Context present, answer not in those docs |
| "Sorry, an error occurred… Expecting value" | Empty/non-JSON LLM response |
| WebUI "Retrieved N sources" but agent sees fewer | Empty extraction for one or more files |

Read `reasoning_content` on the OpenAI-compat response when possible.

## 2. WebUI attachments path

**Check extraction** (inside `open-webui` container):

- File records live in `/app/backend/data/webui.db` table `file`.
- Extracted text is in `data` JSON → `content` field. Empty/whitespace → doc won't inject useful `<source>` text.

**Common fixes**

- `CONTENT_EXTRACTION_ENGINE=docling`, `DOCLING_SERVER_URL` → compose service `docling-serve:5001`
- WebUI `PersistentConfig` may ignore new env vars until DB updated or volume reset — verify runtime config, not just compose file
- User must **re-attach** files after extraction fix

**Message format query-agent expects**

- `<source id="1" name="file.pdf">…extracted text…</source>` inside the user message
- Parser: `query-agent/app/usecases/parse_webui_rag.py`

## 3. Indexed search path

```bash
curl -s http://localhost:8080/documents
```

If `[]`, ingest hasn't run — chat attachments alone won't populate the index.

Ingest:

```bash
curl -X POST http://localhost:8080/ingest -F "file=@doc.pdf"
```

## 4. query-agent direct test

Bypass WebUI — POST to `http://localhost:8000/v1/chat/completions` with a minimal `<source>` tag containing known text. If that works, the bug is upstream (WebUI extraction/format), not the graph.

## 5. LLM gateway

- Large multi-document prompts can return empty bodies → JSON parse error in `app/adapters/llm_langchain.py`
- Retry; check gateway logs; context budgeting is in `app/usecases/context_budget.py`

## 6. Decision tree

```
User question fails
├─ reasoning hits=0 ?
│  ├─ yes → WebUI extraction OR no ingest OR parse_webui_rag mismatch
│  └─ no  → content doesn't contain answer OR LLM abstained
└─ exception in answer ?
   └─ LLM empty/malformed JSON → gateway or context size
```

Stop at the first broken layer; don't patch downstream symptoms.
