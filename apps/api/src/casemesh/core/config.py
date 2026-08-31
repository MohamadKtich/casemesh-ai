from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CaseMesh AI"
    app_version: str = "0.7.0"
    app_env: Literal["local", "test", "cloud"] = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://casemesh:casemesh_local@localhost:5432/casemesh"
    document_storage_root: str = "data/raw"
    max_upload_bytes: int = 10 * 1024 * 1024
    chunk_max_chars: int = 1200
    chunk_overlap_chars: int = 200

    # Phase 23: local-first embeddings + hybrid retrieval
    embedding_provider: Literal["ollama"] = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768
    retrieval_candidate_limit: int = 20
    retrieval_rrf_k: int = 60
    retrieval_vector_weight: float = 0.65
    retrieval_keyword_weight: float = 0.35

    # Phase 24: grounded local answer synthesis
    generation_provider: Literal["ollama"] = "ollama"
    generation_model: str = "qwen3:8b"
    generation_temperature: float = 0.1
    generation_max_tokens: int = 700
    answer_context_max_chars: int = 12000
    answer_source_max_chars: int = 4000

    # Phase 25: investigation workflow orchestration
    workflow_retrieval_top_k: int = 5
    workflow_max_retries: int = 1
    workflow_evidence_excerpt_chars: int = 600

    # Phase 26: durable HITL approval + policy guardrails
    approval_interrupt_question: str = (
        "A human reviewer must approve this sensitive action before execution."
    )
    approval_allow_internal_note_without_review: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
