from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = "sk-placeholder"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1500
    llm_timeout: int = 60
    query_agent_port: int = 8000
    document_index_url: str = "http://document-index:8080"
    document_index_api_version: str = "1"
    document_index_timeout: int = 120
    openai_compat_memory_window: int = 5
    agent_top_k: int = 8
    agent_min_score: float = 0.3
    agent_max_refines: int = 1
    agent_max_context_chars: int = 12000
    agent_min_confidence: float = 0.3
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/nlq"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse:3000"
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "nlq-query-agent"


settings = Settings()
