from uuid import UUID

import pytest

from casemesh.alerts import (
    AlertDispatcher,
    AlertEvent,
    AlertPublishResult,
)

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")


class SuccessfulPublisher:
    provider_name = "successful-provider"

    async def publish(
        self,
        event: AlertEvent,
    ) -> AlertPublishResult:
        return AlertPublishResult(
            provider=self.provider_name,
            event_type=event.event_type,
            delivery_status="published",
            message_id="synthetic-message-id",
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class FailingPublisher:
    provider_name = "failing-provider"

    async def publish(
        self,
        event: AlertEvent,
    ) -> AlertPublishResult:
        del event

        raise RuntimeError("synthetic transport detail that must not be persisted")

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


def _event() -> AlertEvent:
    return AlertEvent(
        event_type="APPROVAL_REQUIRED",
        severity="high",
        source="action",
        case_id=CASE_ID,
        reason_codes=("HIGH_RISK_ACTION",),
    )


@pytest.mark.asyncio
async def test_disabled_dispatcher_is_noop() -> None:
    dispatcher = AlertDispatcher(None)

    result = await dispatcher.dispatch(_event())

    assert result.status == ("disabled")

    assert result.attempted is False
    assert result.delivered is False
    assert result.provider is None
    assert result.message_id is None
    assert result.error_type is None


@pytest.mark.asyncio
async def test_successful_dispatcher_returns_provider_result() -> None:
    dispatcher = AlertDispatcher(SuccessfulPublisher())

    result = await dispatcher.dispatch(_event())

    assert result.status == ("published")

    assert result.attempted is True
    assert result.delivered is True

    assert result.provider == ("successful-provider")

    assert result.message_id == ("synthetic-message-id")

    assert result.error_type is None


@pytest.mark.asyncio
async def test_publisher_failure_is_isolated() -> None:
    dispatcher = AlertDispatcher(FailingPublisher())

    result = await dispatcher.dispatch(_event())

    assert result.status == "failed"
    assert result.attempted is True
    assert result.delivered is False

    assert result.provider == ("failing-provider")

    assert result.message_id is None

    assert result.error_type == ("RuntimeError")


@pytest.mark.asyncio
async def test_failure_result_does_not_persist_exception_message() -> None:
    dispatcher = AlertDispatcher(FailingPublisher())

    result = await dispatcher.dispatch(_event())

    serialized = repr(result)

    assert "synthetic transport detail" not in serialized
