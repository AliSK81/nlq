from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    platform_port: int = 8080
    extractor: str = "docling"
    docling_url: str = "http://docling-serve:5001"
    tika_url: str = "http://tika:9998"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    hybrid_search: bool = True
    sparse_embedding_model: str = "Qdrant/bm25"
    reranker: str = "fastembed"
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    rerank_candidate_multiplier: int = 4
    chunk_target_tokens: int = 512
    chunk_overlap_tokens: int = 64
    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 50
    ingest_worker_concurrency: int = 2
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "document_chunks"
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/nlq"
    database_enabled: int = 1


settings = Settings()
