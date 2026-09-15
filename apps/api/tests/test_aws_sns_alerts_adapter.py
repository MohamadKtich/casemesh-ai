import json
import sys
import time
from uuid import UUID

import pytest

from casemesh.alerts import AlertEvent
from casemesh.core.config import Settings
from casemesh.integrations.aws import (
    build_aws_intelligence_gateway,
)
from casemesh.integrations.aws.sns_alerts import (
    SNSAlertPublisher,
    SNSAlertTimeoutError,
    build_aws_alert_publisher,
)

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")

RUN_ID = UUID("22222222-2222-2222-2222-222222222222")

TOPIC_ARN = "arn:aws:sns:me-central-1:123456789012:casemesh-alerts"


class FakeSNSClient:
    def __init__(
        self,
    ) -> None:
        self.calls: list[dict[str, object]] = []

    def publish(
        self,
        **kwargs: object,
    ) -> object:
        self.calls.append(kwargs)

        return {
            "MessageId": "synthetic-message-id",
        }


class InvalidSNSClient:
    def publish(
        self,
        **kwargs: object,
    ) -> object:
        del kwargs

        return {}


class NonMappingSNSClient:
    def publish(
        self,
        **kwargs: object,
    ) -> object:
        del kwargs

        return "not-a-mapping"


class SlowSNSClient:
    def publish(
        self,
        **kwargs: object,
    ) -> object:
        del kwargs

        time.sleep(0.05)

        return {
            "MessageId": "too-late",
        }


class RecordingClientFactory:
    def __init__(
        self,
        client: object,
    ) -> None:
        self.client = client
        self.calls: list[tuple[str, str]] = []

    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        self.calls.append(
            (
                service_name,
                region_name,
            )
        )

        return self.client


def _event() -> AlertEvent:
    return AlertEvent(
        event_type=("SECOND_REVIEW_DISAGREEMENT"),
        severity="high",
        source="second_review",
        case_id=CASE_ID,
        investigation_run_id=RUN_ID,
        reason_codes=("review_disagreed",),
        risk_level="high",
        status="completed",
    )


@pytest.mark.asyncio
async def test_sns_adapter_publishes_only_safe_contract_payload() -> None:
    client = FakeSNSClient()

    publisher = SNSAlertPublisher(
        client=client,
        topic_arn=TOPIC_ARN,
        timeout_seconds=1.0,
    )

    event = _event()

    result = await publisher.publish(event)

    assert result.delivery_status == ("published")

    assert result.message_id == ("synthetic-message-id")

    assert len(client.calls) == 1

    call = client.calls[0]

    assert call["TopicArn"] == TOPIC_ARN

    assert call["Subject"] == ("[CaseMesh] SECOND_REVIEW_DISAGREEMENT")

    raw_message = call["Message"]

    assert isinstance(
        raw_message,
        str,
    )

    payload = json.loads(raw_message)

    assert payload == (event.payload())

    assert "evidence" not in payload
    assert "findings" not in payload
    assert "payload" not in payload
    assert "rationale" not in payload


@pytest.mark.asyncio
async def test_sns_adapter_rejects_missing_message_id() -> None:
    publisher = SNSAlertPublisher(
        client=InvalidSNSClient(),
        topic_arn=TOPIC_ARN,
        timeout_seconds=1.0,
    )

    with pytest.raises(
        RuntimeError,
        match="valid MessageId",
    ):
        await publisher.publish(
            AlertEvent(
                event_type="APPROVAL_REQUIRED",
                severity="high",
                source="action",
                case_id=CASE_ID,
            )
        )


@pytest.mark.asyncio
async def test_sns_adapter_rejects_non_mapping_response() -> None:
    publisher = SNSAlertPublisher(
        client=NonMappingSNSClient(),
        topic_arn=TOPIC_ARN,
        timeout_seconds=1.0,
    )

    with pytest.raises(
        RuntimeError,
        match="non-object response",
    ):
        await publisher.publish(_event())


@pytest.mark.asyncio
async def test_sns_adapter_enforces_operation_timeout() -> None:
    publisher = SNSAlertPublisher(
        client=SlowSNSClient(),
        topic_arn=TOPIC_ARN,
        timeout_seconds=0.01,
    )

    with pytest.raises(
        SNSAlertTimeoutError,
        match="timed out",
    ):
        await publisher.publish(_event())


@pytest.mark.asyncio
async def test_sns_adapter_health_is_configuration_only() -> None:
    publisher = SNSAlertPublisher(
        client=FakeSNSClient(),
        topic_arn=TOPIC_ARN,
        timeout_seconds=1.0,
    )

    health = await publisher.health()

    assert health["network_checked"] is False

    assert health["delivery_mode"] == "sns"


def test_sdk_factory_routes_sns_through_ai_region_without_boto3() -> None:
    sys.modules.pop(
        "boto3",
        None,
    )

    client = FakeSNSClient()

    factory = RecordingClientFactory(client)

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_sns_alerts_enabled=True,
        aws_human_alert_topic_arn=(TOPIC_ARN),
    )

    gateway = build_aws_intelligence_gateway(
        settings,
        client_factory=factory,
    )

    publisher = build_aws_alert_publisher(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        publisher,
        SNSAlertPublisher,
    )

    assert factory.calls == [
        (
            "sns",
            "me-central-1",
        )
    ]

    assert "boto3" not in sys.modules


@pytest.mark.asyncio
async def test_standard_topic_does_not_send_fifo_fields() -> None:
    client = FakeSNSClient()

    publisher = SNSAlertPublisher(
        client=client,
        topic_arn=TOPIC_ARN,
        timeout_seconds=1.0,
    )

    await publisher.publish(_event())

    assert len(client.calls) == 1

    call = client.calls[0]

    assert "MessageGroupId" not in call

    assert "MessageDeduplicationId" not in call


@pytest.mark.asyncio
async def test_fifo_topic_uses_deterministic_deduplication() -> None:
    client = FakeSNSClient()

    fifo_topic_arn = f"{TOPIC_ARN}.fifo"

    publisher = SNSAlertPublisher(
        client=client,
        topic_arn=fifo_topic_arn,
        timeout_seconds=1.0,
    )

    event = _event()

    await publisher.publish(event)

    await publisher.publish(event)

    changed = AlertEvent(
        event_type=("SECOND_REVIEW_DISAGREEMENT"),
        severity="critical",
        source="second_review",
        case_id=CASE_ID,
        investigation_run_id=RUN_ID,
        reason_codes=("review_disagreed",),
        risk_level="critical",
        status="completed",
    )

    await publisher.publish(changed)

    assert len(client.calls) == 3

    first = client.calls[0]
    second = client.calls[1]
    third = client.calls[2]

    assert first["TopicArn"] == fifo_topic_arn

    assert first["MessageDeduplicationId"] == event.deduplication_key()

    assert second["MessageDeduplicationId"] == event.deduplication_key()

    assert first["MessageDeduplicationId"] == second["MessageDeduplicationId"]

    assert third["MessageDeduplicationId"] == changed.deduplication_key()

    assert third["MessageDeduplicationId"] != first["MessageDeduplicationId"]

    assert first["MessageGroupId"] == second["MessageGroupId"]

    # Different alert content for the same case
    # stays in the same FIFO ordering group.
    assert third["MessageGroupId"] == first["MessageGroupId"]

    group_id = first["MessageGroupId"]

    assert isinstance(
        group_id,
        str,
    )

    assert group_id.startswith("casemesh-")

    assert len(group_id) <= 128
