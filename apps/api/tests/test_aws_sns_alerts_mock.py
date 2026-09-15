import sys
from uuid import UUID

import pytest

from casemesh.alerts import AlertEvent
from casemesh.core.config import Settings
from casemesh.integrations.aws import (
    build_aws_intelligence_gateway,
)
from casemesh.integrations.aws.sns_alerts import (
    MockSNSAlertPublisher,
    build_aws_alert_publisher,
)

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
        aws_sns_alerts_enabled=True,
        aws_human_alert_topic_arn=("arn:aws:sns:me-central-1:123456789012:casemesh-alerts"),
    )


def test_disabled_alert_factory_returns_none() -> None:
    settings = Settings(
        _env_file=None,
    )

    gateway = build_aws_intelligence_gateway(settings)

    assert (
        build_aws_alert_publisher(
            settings=settings,
            gateway=gateway,
        )
        is None
    )


def test_mock_factory_does_not_import_boto3() -> None:
    sys.modules.pop(
        "boto3",
        None,
    )

    settings = _settings()

    gateway = build_aws_intelligence_gateway(settings)

    publisher = build_aws_alert_publisher(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        publisher,
        MockSNSAlertPublisher,
    )

    assert "boto3" not in sys.modules


@pytest.mark.asyncio
async def test_mock_publish_is_deterministic_and_offline() -> None:
    publisher = MockSNSAlertPublisher(
        topic_arn=("arn:aws:sns:me-central-1:123456789012:casemesh-alerts")
    )

    event = AlertEvent(
        event_type="GUARDRAIL_BLOCK",
        severity="critical",
        source="guardrail",
        case_id=CASE_ID,
        reason_codes=("guardrail_blocked",),
    )

    first = await publisher.publish(event)

    second = await publisher.publish(event)

    assert first.delivery_status == ("simulated")

    assert second.delivery_status == ("simulated")

    assert first.message_id == (second.message_id)

    assert publisher.published_events == (
        event,
        event,
    )

    assert "boto3" not in sys.modules


@pytest.mark.asyncio
async def test_mock_health_never_claims_network_check() -> None:
    publisher = MockSNSAlertPublisher(
        topic_arn=("arn:aws:sns:me-central-1:123456789012:casemesh-alerts")
    )

    health = await publisher.health()

    assert health["network_checked"] is False

    assert health["delivery_mode"] == "mock"


@pytest.mark.asyncio
async def test_mock_message_id_uses_alert_deduplication_key() -> None:
    publisher = MockSNSAlertPublisher(
        topic_arn=("arn:aws:sns:me-central-1:123456789012:casemesh-alerts")
    )

    event = AlertEvent(
        event_type="GUARDRAIL_BLOCK",
        severity="critical",
        source="guardrail",
        case_id=CASE_ID,
        reason_codes=("guardrail_blocked",),
    )

    result = await publisher.publish(event)

    assert result.message_id == (f"mock-{event.deduplication_key()[:24]}")
