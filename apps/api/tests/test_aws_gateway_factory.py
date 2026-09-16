import sys

import pytest
from pydantic import ValidationError

from casemesh.core.config import Settings
from casemesh.integrations.aws import (
    AWSIntelligenceGateway,
    MockAWSClient,
    build_aws_intelligence_gateway,
)


def test_aws_client_mode_defaults_to_mock() -> None:
    settings = Settings(_env_file=None)

    assert settings.aws_client_mode == "mock"


def test_invalid_aws_client_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            aws_client_mode="invalid",
        )


def test_gateway_factory_defaults_to_offline_mock_mode() -> None:
    settings = Settings(_env_file=None)

    gateway = build_aws_intelligence_gateway(settings)

    assert isinstance(gateway, AWSIntelligenceGateway)

    status = gateway.status()

    assert status.client_mode == "mock"
    assert status.enabled is False
    assert status.network_checked is False


def test_mock_bedrock_client_is_deterministic_and_offline() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model",
    )

    gateway = build_aws_intelligence_gateway(settings)

    first = gateway.bedrock_runtime_client()
    second = gateway.bedrock_runtime_client()

    assert isinstance(first, MockAWSClient)
    assert first is second
    assert first.mode == "mock"
    assert first.service_name == "bedrock-runtime"
    assert first.region_name == "me-central-1"


def test_mock_document_clients_use_document_region() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket="synthetic-bucket",
        aws_textract_completion_topic_arn="synthetic-topic",
        aws_textract_queue_url="synthetic-queue",
    )

    gateway = build_aws_intelligence_gateway(settings)

    s3_client = gateway.s3_staging_client()
    textract_client = gateway.textract_client()
    sqs_client = gateway.sqs_client()

    assert isinstance(s3_client, MockAWSClient)
    assert isinstance(textract_client, MockAWSClient)
    assert isinstance(sqs_client, MockAWSClient)

    assert s3_client.region_name == "eu-west-1"
    assert textract_client.region_name == "eu-west-1"
    assert sqs_client.region_name == "eu-west-1"


def test_mock_human_alert_client_uses_ai_region() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
        aws_sns_alerts_enabled=True,
        aws_human_alert_topic_arn="synthetic-topic",
    )

    gateway = build_aws_intelligence_gateway(settings)

    client = gateway.human_alerts_sns_client()

    assert isinstance(client, MockAWSClient)
    assert client.service_name == "sns"
    assert client.region_name == "me-central-1"


def test_sdk_mode_factory_does_not_import_boto3_until_client_use() -> None:
    sys.modules.pop("boto3", None)

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=False,
        aws_client_mode="sdk",
    )

    gateway = build_aws_intelligence_gateway(settings)

    gateway.status()

    assert "boto3" not in sys.modules


@pytest.mark.asyncio
async def test_health_reports_mock_mode_without_network_check() -> None:
    settings = Settings(
        _env_file=None,
        aws_client_mode="mock",
    )

    gateway = build_aws_intelligence_gateway(settings)

    health = await gateway.health()

    assert health["client_mode"] == "mock"
    assert health["network_checked"] is False
