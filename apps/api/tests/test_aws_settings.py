import pytest
from pydantic import ValidationError

from casemesh.core.config import Settings


def test_aws_features_are_disabled_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.aws_intelligence_enabled is False
    assert settings.aws_textract_enabled is False
    assert settings.aws_async_processing_enabled is False
    assert settings.aws_bedrock_review_enabled is False
    assert settings.aws_bedrock_guardrails_enabled is False
    assert settings.aws_sns_alerts_enabled is False


def test_aws_regions_have_safe_explicit_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.aws_ai_region == "me-central-1"
    assert settings.aws_document_region == "eu-west-1"


@pytest.mark.parametrize(
    "feature",
    [
        "aws_textract_enabled",
        "aws_async_processing_enabled",
        "aws_bedrock_review_enabled",
        "aws_bedrock_guardrails_enabled",
        "aws_sns_alerts_enabled",
    ],
)
def test_aws_capability_requires_master_switch(feature: str) -> None:
    with pytest.raises(
        ValidationError,
        match="AWS capabilities cannot be enabled",
    ):
        Settings(
            _env_file=None,
            **{feature: True},
        )


def test_bedrock_review_requires_model_id() -> None:
    with pytest.raises(
        ValidationError,
        match="aws_bedrock_model_id is required",
    ):
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_bedrock_review_enabled=True,
        )


def test_bedrock_review_accepts_model_id() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model-id",
    )

    assert settings.aws_bedrock_review_enabled is True


def test_guardrails_require_bedrock_review() -> None:
    with pytest.raises(
        ValidationError,
        match="Guardrails require",
    ):
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_bedrock_guardrails_enabled=True,
            aws_bedrock_guardrail_id="synthetic-guardrail",
            aws_bedrock_guardrail_version="1",
        )


def test_guardrails_require_guardrail_identifiers() -> None:
    with pytest.raises(
        ValidationError,
        match="aws_bedrock_guardrail_id is required",
    ):
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_bedrock_review_enabled=True,
            aws_bedrock_model_id="synthetic-model-id",
            aws_bedrock_guardrails_enabled=True,
        )


def test_valid_bedrock_guardrail_configuration() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model-id",
        aws_bedrock_guardrails_enabled=True,
        aws_bedrock_guardrail_id="synthetic-guardrail",
        aws_bedrock_guardrail_version="1",
    )

    assert settings.aws_bedrock_guardrails_enabled is True


def test_textract_requires_async_processing() -> None:
    with pytest.raises(
        ValidationError,
        match="Textract requires",
    ):
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_textract_enabled=True,
            aws_textract_bucket="synthetic-bucket",
            aws_textract_completion_topic_arn="synthetic-topic",
            aws_textract_queue_url="synthetic-queue",
        )


def test_textract_requires_processing_resources() -> None:
    with pytest.raises(
        ValidationError,
        match="Missing required AWS Textract settings",
    ):
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_async_processing_enabled=True,
            aws_textract_enabled=True,
        )


def test_valid_textract_configuration() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket="synthetic-bucket",
        aws_textract_completion_topic_arn="synthetic-topic",
        aws_textract_queue_url="synthetic-queue",
    )

    assert settings.aws_textract_enabled is True


def test_sns_alerts_require_topic() -> None:
    with pytest.raises(
        ValidationError,
        match="aws_human_alert_topic_arn is required",
    ):
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_sns_alerts_enabled=True,
        )


@pytest.mark.parametrize(
    ("setting_name", "invalid_value"),
    [
        ("aws_request_timeout_seconds", 0),
        ("aws_max_reviews_per_investigation", 0),
        ("aws_max_textract_pages", 0),
    ],
)
def test_aws_operational_limits_must_be_positive(
    setting_name: str,
    invalid_value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            **{setting_name: invalid_value},
        )


def test_aws_identity_mode_defaults_to_default_chain() -> None:
    settings = Settings(
        _env_file=None,
    )

    assert settings.aws_identity_mode == "default_chain"

    assert settings.aws_federated_role_arn == ""

    assert settings.aws_federated_audience == ""

    assert settings.azure_managed_identity_client_id == ""

    assert settings.aws_federated_role_session_name == "casemesh-api"


def test_default_chain_does_not_require_federation_settings() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_identity_mode="default_chain",
    )

    assert settings.aws_identity_mode == "default_chain"


def test_azure_federated_identity_requires_master_switch() -> None:
    with pytest.raises(
        ValueError,
        match="aws_intelligence_enabled",
    ):
        Settings(
            _env_file=None,
            aws_identity_mode=("azure_federated"),
            aws_client_mode="sdk",
            aws_federated_role_arn=("arn:aws:iam::123456789012:role/CaseMeshRuntime"),
            aws_federated_audience=("api://casemesh-aws"),
            azure_managed_identity_client_id=("11111111-1111-1111-1111-111111111111"),
        )


def test_azure_federated_identity_requires_sdk_mode() -> None:
    with pytest.raises(
        ValueError,
        match="aws_client_mode='sdk'",
    ):
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_identity_mode=("azure_federated"),
            aws_client_mode="mock",
            aws_federated_role_arn=("arn:aws:iam::123456789012:role/CaseMeshRuntime"),
            aws_federated_audience=("api://casemesh-aws"),
            azure_managed_identity_client_id=("11111111-1111-1111-1111-111111111111"),
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "aws_federated_role_arn",
        "aws_federated_audience",
        "azure_managed_identity_client_id",
        "aws_federated_role_session_name",
    ),
)
def test_azure_federated_identity_requires_complete_configuration(
    field_name: str,
) -> None:
    values: dict[str, object] = {
        "_env_file": None,
        "aws_intelligence_enabled": True,
        "aws_client_mode": "sdk",
        "aws_identity_mode": ("azure_federated"),
        "aws_federated_role_arn": ("arn:aws:iam::123456789012:role/CaseMeshRuntime"),
        "aws_federated_audience": ("api://casemesh-aws"),
        "azure_managed_identity_client_id": ("11111111-1111-1111-1111-111111111111"),
        "aws_federated_role_session_name": ("casemesh-api"),
    }

    values[field_name] = " "

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        Settings(
            **values,
        )


def test_valid_azure_federated_identity_configuration() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_identity_mode=("azure_federated"),
        aws_federated_role_arn=("arn:aws:iam::123456789012:role/CaseMeshRuntime"),
        aws_federated_audience=("api://casemesh-aws"),
        azure_managed_identity_client_id=("11111111-1111-1111-1111-111111111111"),
        aws_federated_role_session_name=("casemesh-api"),
    )

    assert settings.aws_identity_mode == "azure_federated"
