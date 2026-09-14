import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import Protocol, cast

from casemesh.alerts import (
    AlertDispatcher,
    AlertEvent,
    AlertPublisher,
    AlertPublishResult,
)
from casemesh.core.config import Settings
from casemesh.integrations.aws.factory import build_aws_intelligence_gateway
from casemesh.integrations.aws.gateway import (
    AWSIntelligenceGateway,
)


class SNSClientProtocol(Protocol):
    def publish(
        self,
        **kwargs: object,
    ) -> object:
        """Publish an SNS message."""


class SNSAlertTimeoutError(RuntimeError):
    """Raised when an SNS publish exceeds the configured timeout."""


class MockSNSAlertPublisher:
    """Deterministic zero-network human-alert publisher."""

    provider_name = "aws-sns-alerts-mock"

    def __init__(
        self,
        *,
        topic_arn: str,
    ) -> None:
        normalized_topic = topic_arn.strip()

        if not normalized_topic:
            raise ValueError("Mock SNS alert topic ARN must not be blank.")

        self._topic_arn = normalized_topic
        self._events: list[AlertEvent] = []

    @property
    def published_events(
        self,
    ) -> tuple[AlertEvent, ...]:
        return tuple(self._events)

    async def publish(
        self,
        event: AlertEvent,
    ) -> AlertPublishResult:
        self._events.append(event)

        serialized = json.dumps(
            event.payload(),
            separators=(",", ":"),
            sort_keys=True,
        )

        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return AlertPublishResult(
            provider=self.provider_name,
            event_type=event.event_type,
            delivery_status="simulated",
            message_id=(f"mock-{digest[:24]}"),
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
            "delivery_mode": "mock",
            "topic_configured": True,
            "published_count": len(self._events),
        }


class SNSAlertPublisher:
    """AWS SNS human-alert adapter.

    The publisher sends only AlertEvent.payload(), whose contract excludes
    raw case content, evidence, prompts, findings, and action payloads.
    """

    provider_name = "aws-sns-alerts"

    def __init__(
        self,
        *,
        client: SNSClientProtocol,
        topic_arn: str,
        timeout_seconds: float,
    ) -> None:
        normalized_topic = topic_arn.strip()

        if not normalized_topic:
            raise ValueError("SNS alert topic ARN must not be blank.")

        if timeout_seconds <= 0:
            raise ValueError("SNS alert timeout must be greater than zero.")

        self._client = client
        self._topic_arn = normalized_topic
        self._timeout_seconds = timeout_seconds

    async def publish(
        self,
        event: AlertEvent,
    ) -> AlertPublishResult:
        message = json.dumps(
            event.payload(),
            separators=(",", ":"),
            sort_keys=True,
        )

        subject = f"[CaseMesh] {event.event_type}"

        try:
            raw_response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.publish,
                    TopicArn=self._topic_arn,
                    Subject=subject,
                    Message=message,
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise SNSAlertTimeoutError("AWS SNS alert publish timed out.") from exc

        response = self._require_mapping(raw_response)

        raw_message_id = response.get("MessageId")

        if (
            not isinstance(
                raw_message_id,
                str,
            )
            or not raw_message_id.strip()
        ):
            raise RuntimeError("AWS SNS publish response did not contain a valid MessageId.")

        return AlertPublishResult(
            provider=self.provider_name,
            event_type=event.event_type,
            delivery_status="published",
            message_id=raw_message_id.strip(),
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
            "delivery_mode": "sns",
            "topic_configured": True,
        }

    @staticmethod
    def _require_mapping(
        response: object,
    ) -> Mapping[str, object]:
        if not isinstance(
            response,
            Mapping,
        ):
            raise RuntimeError("AWS SNS publish returned a non-object response.")

        return cast(
            Mapping[str, object],
            response,
        )


def build_aws_alert_publisher(
    *,
    settings: Settings,
    gateway: AWSIntelligenceGateway,
) -> AlertPublisher | None:
    """Build the configured human-alert provider.

    Disabled capability returns None.
    Mock mode never requests an AWS client.
    SDK mode obtains SNS only through the AWS gateway boundary.
    """

    if not settings.aws_sns_alerts_enabled:
        return None

    topic_arn = settings.aws_human_alert_topic_arn

    if settings.aws_client_mode == "mock":
        return MockSNSAlertPublisher(
            topic_arn=topic_arn,
        )

    client = cast(
        SNSClientProtocol,
        gateway.human_alerts_sns_client(),
    )

    return SNSAlertPublisher(
        client=client,
        topic_arn=topic_arn,
        timeout_seconds=(settings.aws_request_timeout_seconds),
    )


def build_aws_alert_dispatcher(
    *,
    settings: Settings,
) -> AlertDispatcher:
    """Build the optional best-effort human-alert boundary."""

    if not settings.aws_sns_alerts_enabled:
        return AlertDispatcher(None)

    gateway = build_aws_intelligence_gateway(settings)

    publisher = build_aws_alert_publisher(
        settings=settings,
        gateway=gateway,
    )

    return AlertDispatcher(publisher)
