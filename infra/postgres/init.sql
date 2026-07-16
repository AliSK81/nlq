CREATE TABLE documents (
    id              UUID PRIMARY KEY,
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    name            TEXT NOT NULL,
    mime_type       TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    size_bytes      BIGINT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'UPLOADED',
    error           TEXT,
    extractor       TEXT,
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
    section_path    TEXT,
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

CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    username TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    sender TEXT,
    text TEXT,
    intent TEXT,
    citations JSONB,
    tokens_used INT,
    created_at TIMESTAMPTZ DEFAULT now()
);
