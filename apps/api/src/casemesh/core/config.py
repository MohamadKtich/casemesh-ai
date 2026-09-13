from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CaseMesh AI"
    app_version: str = "0.7.0"
    app_env: Literal["local", "test", "cloud"] = "local"
    log_level: str = "INFO"

    # Comma-separated browser origins allowed to call the REST API.
    # Keep this explicit. Do not use "*" with authenticated browser APIs.
    cors_allowed_origins: str = "http://localhost:3000"

    database_url: str = "postgresql+asyncpg://casemesh:casemesh_local@localhost:5432/casemesh"

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
    hf_inference_base_url: str = "https://router.huggingface.co/hf-inference"

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
    # Phase 37: AWS specialized intelligence extension.
    #
    # Master switch remains disabled by default. Individual capabilities
    # must also be explicitly enabled before any AWS integration can run.
    aws_intelligence_enabled: bool = False

    # Mock mode is deterministic, offline, and cost-free.
    # SDK mode permits real boto3 clients when a capability is enabled.
    aws_client_mode: Literal["mock", "sdk"] = "mock"

    # Bedrock, Guardrails, and human-escalation services.
    aws_ai_region: str = "me-central-1"

    # Textract is not currently available in me-central-1.
    # S3 staging, Textract, completion SNS, and processing SQS must use
    # the same supported document-processing region.
    aws_document_region: str = "eu-west-1"

    aws_textract_enabled: bool = False
    aws_async_processing_enabled: bool = False
    aws_bedrock_review_enabled: bool = False
    aws_bedrock_guardrails_enabled: bool = False
    aws_sns_alerts_enabled: bool = False

    # Resource identifiers remain empty until real AWS validation.
    aws_bedrock_model_id: str = ""
    aws_bedrock_guardrail_id: str = ""
    aws_bedrock_guardrail_version: str = ""

    aws_textract_bucket: str = ""
    aws_textract_completion_topic_arn: str = ""
    aws_textract_notification_role_arn: str = ""
    aws_textract_queue_url: str = ""
    aws_human_alert_topic_arn: str = ""

    # Defensive operational limits.
    aws_request_timeout_seconds: float = 30.0
    aws_max_reviews_per_investigation: int = 1
    aws_max_textract_pages: int = 20

    @model_validator(mode="after")
    def validate_aws_configuration(self) -> "Settings":
        aws_capabilities_enabled = any(
            (
                self.aws_textract_enabled,
                self.aws_async_processing_enabled,
                self.aws_bedrock_review_enabled,
                self.aws_bedrock_guardrails_enabled,
                self.aws_sns_alerts_enabled,
            )
        )

        if aws_capabilities_enabled and not self.aws_intelligence_enabled:
            raise ValueError(
                "AWS capabilities cannot be enabled while aws_intelligence_enabled is false."
            )

        if self.aws_request_timeout_seconds <= 0:
            raise ValueError("aws_request_timeout_seconds must be greater than 0.")

        if self.aws_max_reviews_per_investigation <= 0:
            raise ValueError("aws_max_reviews_per_investigation must be greater than 0.")

        if self.aws_max_textract_pages <= 0:
            raise ValueError("aws_max_textract_pages must be greater than 0.")

        if self.aws_bedrock_review_enabled and not self.aws_bedrock_model_id.strip():
            raise ValueError("aws_bedrock_model_id is required when AWS Bedrock review is enabled.")

        if self.aws_bedrock_guardrails_enabled:
            if not self.aws_bedrock_review_enabled:
                raise ValueError("AWS Bedrock Guardrails require aws_bedrock_review_enabled=true.")

            if not self.aws_bedrock_guardrail_id.strip():
                raise ValueError(
                    "aws_bedrock_guardrail_id is required when AWS Bedrock Guardrails are enabled."
                )

            if not self.aws_bedrock_guardrail_version.strip():
                raise ValueError(
                    "aws_bedrock_guardrail_version is required when "
                    "AWS Bedrock Guardrails are enabled."
                )

        if self.aws_textract_enabled:
            if not self.aws_async_processing_enabled:
                raise ValueError("AWS Textract requires aws_async_processing_enabled=true.")

            missing_textract_settings = [
                name
                for name, value in (
                    ("aws_textract_bucket", self.aws_textract_bucket),
                    (
                        "aws_textract_completion_topic_arn",
                        self.aws_textract_completion_topic_arn,
                    ),
                    ("aws_textract_queue_url", self.aws_textract_queue_url),
                )
                if not value.strip()
            ]

            if missing_textract_settings:
                missing = ", ".join(missing_textract_settings)
                raise ValueError(f"Missing required AWS Textract settings: {missing}")

        if self.aws_sns_alerts_enabled and not self.aws_human_alert_topic_arn.strip():
            raise ValueError(
                "aws_human_alert_topic_arn is required when AWS SNS alerts are enabled."
            )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
