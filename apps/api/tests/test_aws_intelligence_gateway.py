import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws import AWSIntelligenceGateway


def test_gateway_is_fully_disabled_by_default() -> None:
    settings = Settings(_env_file=None)
    gateway = AWSIntelligenceGateway(settings)

    status = gateway.status()

    assert status.provider == "aws"
    assert status.enabled is False
    assert status.ai_region == "me-central-1"
    assert status.document_region == "eu-west-1"
    assert status.network_checked is False

    assert status.second_review.enabled is False
    assert status.second_review.reason == "master_disabled"

    assert status.guardrails.enabled is False
    assert status.guardrails.reason == "master_disabled"

    assert status.document_intelligence.enabled is False
    assert status.document_intelligence.reason == "master_disabled"

    assert status.async_processing.enabled is False
    assert status.async_processing.reason == "master_disabled"

    assert status.human_alerts.enabled is False
    assert status.human_alerts.reason == "master_disabled"


def test_master_enabled_keeps_individual_features_disabled() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
    )

    gateway = AWSIntelligenceGateway(settings)
    status = gateway.status()

    assert status.enabled is True

    assert status.second_review.enabled is False
    assert status.second_review.reason == "feature_disabled"

    assert status.guardrails.enabled is False
    assert status.guardrails.reason == "feature_disabled"

    assert status.document_intelligence.enabled is False
    assert status.document_intelligence.reason == "feature_disabled"

    assert status.async_processing.enabled is False
    assert status.async_processing.reason == "feature_disabled"

    assert status.human_alerts.enabled is False
    assert status.human_alerts.reason == "feature_disabled"


def test_bedrock_review_capability_can_be_enabled_independently() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model",
    )

    gateway = AWSIntelligenceGateway(settings)
    status = gateway.status()

    assert status.second_review.enabled is True
    assert status.second_review.reason is None

    assert status.guardrails.enabled is False
    assert status.document_intelligence.enabled is False
    assert status.async_processing.enabled is False
    assert status.human_alerts.enabled is False


def test_textract_capabilities_report_valid_configuration() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket="synthetic-bucket",
        aws_textract_completion_topic_arn="synthetic-topic",
        aws_textract_queue_url="synthetic-queue",
    )

    gateway = AWSIntelligenceGateway(settings)
    status = gateway.status()

    assert status.document_intelligence.enabled is True
    assert status.async_processing.enabled is True
    assert status.second_review.enabled is False


def test_human_alert_capability_reports_valid_configuration() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_sns_alerts_enabled=True,
        aws_human_alert_topic_arn="synthetic-topic",
    )

    gateway = AWSIntelligenceGateway(settings)
    status = gateway.status()

    assert status.human_alerts.enabled is True
    assert status.human_alerts.reason is None


@pytest.mark.asyncio
async def test_health_is_offline_and_does_not_claim_network_validation() -> None:
    settings = Settings(_env_file=None)
    gateway = AWSIntelligenceGateway(settings)

    health = await gateway.health()

    assert health["provider"] == "aws"
    assert health["enabled"] is False
    assert health["network_checked"] is False

    regions = health["regions"]
    assert isinstance(regions, dict)
    assert regions["ai"] == "me-central-1"
    assert regions["document"] == "eu-west-1"

    capabilities = health["capabilities"]
    assert isinstance(capabilities, dict)
    assert capabilities["second_review"] is False
    assert capabilities["guardrails"] is False
    assert capabilities["document_intelligence"] is False
    assert capabilities["async_processing"] is False
    assert capabilities["human_alerts"] is False
