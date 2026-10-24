"""Application settings loaded from environment variables / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration for LecturaRAG.

    Every value can be overridden through the environment or a local `.env`
    file. No API key is ever hardcoded; when `LLM_API_KEY` is empty the
    application falls back to its deterministic extractive engine.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "LecturaRAG API"
    app_version: str = "1.0.0"
    environment: str = "development"

    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'lecturarag.db').as_posix()}"
    cors_origins: str = "http://localhost:5173"

    max_upload_mb: int = Field(default=20, ge=1, le=200)
    chunk_size: int = Field(default=500, ge=200, le=4000)
    chunk_overlap: int = Field(default=100, ge=0, le=1000)
    retrieval_top_k: int = Field(default=4, ge=1, le=10)
    embedding_dimensions: int = Field(default=512, ge=128, le=4096)

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1400, ge=256, le=8192)
    llm_timeout_seconds: float = Field(default=45.0, ge=5.0, le=300.0)

    @field_validator("llm_api_key")
    @classmethod
    def _strip_key(cls, value: str) -> str:
        return value.strip()

    @field_validator("llm_base_url")
    @classmethod
    def _normalise_base_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("chunk_overlap")
    @classmethod
    def _overlap_must_be_smaller_than_chunk(cls, value: int, info) -> int:
        chunk_size = info.data.get("chunk_size", 500)
        if value >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
