from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CaseMesh AI"
    app_version: str = "0.7.0"
    app_env: Literal["local", "test", "cloud"] = "local"
    log_level: str = "INFO"

    # Comma-separated browser origins allowed to call the REST API.
    # Keep this explicit. Do not use "*" with authenticated browser APIs.
    cors_allowed_origins: str = "http://localhost:3000"

    database_url: str = (
        "postgresql+asyncpg://casemesh:casemesh_local@localhost:5432/casemesh"
    )

    document_storage_root: str = "data/raw"
    max_upload_bytes: int = 10 * 1024 * 1024

    chunk_max_chars: int = 1200
    chunk_overlap_chars: int = 200

    # Phase 23 / 27d: embeddings + hybrid retrieval
    embedding_provider: Literal[
        "ollama",
        "huggingface",
    ] = "ollama"

    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768

    ollama_base_url: str = "http://127.0.0.1:11434"

    hf_token: str = ""
    hf_inference_base_url: str = (
        "https://router.huggingface.co/hf-inference"
    )

    retrieval_candidate_limit: int = 20
    retrieval_rrf_k: int = 60
    retrieval_vector_weight: float = 0.65
    retrieval_keyword_weight: float = 0.35

    # Phase 24: grounded answer synthesis
    generation_provider: Literal[
        "ollama",
        "huggingface",
    ] = "ollama"

    generation_model: str = "qwen3:8b"
    generation_temperature: float = 0.1
    generation_max_tokens: int = 700

    answer_context_max_chars: int = 12000
    answer_source_max_chars: int = 4000

    # Phase 25: investigation workflow
    workflow_retrieval_top_k: int = 5
    workflow_max_retries: int = 1
    workflow_evidence_excerpt_chars: int = 600

    # Phase 26: HITL + policy
    approval_interrupt_question: str = (
        "A human reviewer must approve this sensitive action before execution."
    )

    approval_allow_internal_note_without_review: bool = True

    # Phase 28: controlled action execution
    action_execution_enabled: bool = False

    action_execution_mode: Literal[
        "dry_run",
        "live",
    ] = "dry_run"

    # Comma-separated allowlist.
    # Keep financially/customer-facing actions out of this list.
    action_execution_live_allowlist: str = "update_case_status"

    # Phase 29: remote MCP transport + authentication.
    # Hostname only. Do not include https:// or a path.
    mcp_public_hostname: str = ""

    # Required for authenticated remote MCP access.
    # Store the real cloud value as a secret.
    mcp_auth_token: str = ""

    # Phase 29C: investigation agent MCP integration.
    investigation_use_mcp: bool = False

    mcp_client_url: str = "http://127.0.0.1:8000/mcp/"

    mcp_client_timeout_seconds: float = 120.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()