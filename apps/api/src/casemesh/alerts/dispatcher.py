from dataclasses import dataclass
from typing import Literal

from casemesh.alerts.contracts import (
    AlertEvent,
    AlertEventType,
    AlertPublisher,
)

AlertDispatchStatus = Literal[
    "disabled",
    "simulated",
    "published",
    "failed",
]


@dataclass(frozen=True, slots=True)
class AlertDispatchResult:
    """Outcome of best-effort alert delivery.

    Provider exception messages are intentionally not persisted because they
    may contain transport, SDK, or infrastructure details.
    """

    event_type: AlertEventType
    status: AlertDispatchStatus
    attempted: bool
    delivered: bool
    provider: str | None = None
    message_id: str | None = None
    error_type: str | None = None


class AlertDispatcher:
    """Best-effort alert boundary.

    Alert delivery is advisory operational signaling. A publisher outage must
    not fail the authoritative CaseMesh investigation, policy, or action flow.
    """

    def __init__(
        self,
        publisher: AlertPublisher | None,
    ) -> None:
        self._publisher = publisher

    async def dispatch(
        self,
        event: AlertEvent,
    ) -> AlertDispatchResult:
        publisher = self._publisher

        if publisher is None:
            return AlertDispatchResult(
                event_type=event.event_type,
                status="disabled",
                attempted=False,
                delivered=False,
            )

        try:
            result = await publisher.publish(event)
        except Exception as exc:
            return AlertDispatchResult(
                event_type=event.event_type,
                status="failed",
                attempted=True,
                delivered=False,
                provider=publisher.provider_name,
                error_type=type(exc).__name__,
            )

        return AlertDispatchResult(
            event_type=event.event_type,
            status=result.delivery_status,
            attempted=True,
            delivered=True,
            provider=result.provider,
            message_id=result.message_id,
        )
