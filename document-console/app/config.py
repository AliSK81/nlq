from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    document_index_url: str = "http://document-index:8080"
    console_host: str = "0.0.0.0"
    console_port: int = 8081
    request_timeout: int = 120


settings = Settings()
