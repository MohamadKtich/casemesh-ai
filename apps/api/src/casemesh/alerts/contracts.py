import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

AlertEventType = Literal[
    "SECOND_REVIEW_DISAGREEMENT",
    "HIGH_RISK_CASE",
    "GUARDRAIL_BLOCK",
    "APPROVAL_REQUIRED",
    "CROSS_CLOUD_FAILURE",
]

AlertSeverity = Literal[
    "warning",
    "high",
    "critical",
]

AlertSource = Literal[
    "second_review",
    "guardrail",
    "action",
    "aws_boundary",
]

AlertDeliveryStatus = Literal[
    "simulated",
    "published",
]


@dataclass(frozen=True, slots=True)
class AlertEvent:
    """Safe human-alert event.

    Deliberately excludes objectives, findings, evidence text, prompts,
    action payloads, customer messages, and other case content.
    """

    event_type: AlertEventType
    severity: AlertSeverity
    source: AlertSource
    case_id: UUID | None = None
    investigation_run_id: UUID | None = None
    action_request_id: UUID | None = None
    reason_codes: tuple[str, ...] = ()
    risk_level: str | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        normalized_reason_codes = tuple(reason_code.strip() for reason_code in self.reason_codes)

        if any(not reason_code for reason_code in normalized_reason_codes):
            raise ValueError("Alert reason codes must not contain blank values.")

        object.__setattr__(
            self,
            "reason_codes",
            normalized_reason_codes,
        )

        for field_name in (
            "risk_level",
            "status",
        ):
            value = getattr(
                self,
                field_name,
            )

            if value is None:
                continue

            normalized = value.strip()

            object.__setattr__(
                self,
                field_name,
                normalized or None,
            )

    def deduplication_key(self) -> str:
        """Return a deterministic hash of safe alert metadata only."""
        serialized = json.dumps(
            self.payload(),
            separators=(",", ":"),
            sort_keys=True,
        )

        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def payload(self) -> dict[str, object]:
        """Return the intentionally minimal serialization surface."""

        payload: dict[str, object] = {
            "event_type": self.event_type,
            "severity": self.severity,
            "source": self.source,
            "reason_codes": list(self.reason_codes),
        }

        if self.case_id is not None:
            payload["case_id"] = str(self.case_id)

        if self.investigation_run_id is not None:
            payload["investigation_run_id"] = str(self.investigation_run_id)

        if self.action_request_id is not None:
            payload["action_request_id"] = str(self.action_request_id)

        if self.risk_level is not None:
            payload["risk_level"] = self.risk_level

        if self.status is not None:
            payload["status"] = self.status

        return payload


@dataclass(frozen=True, slots=True)
class AlertPublishResult:
    provider: str
    event_type: AlertEventType
    delivery_status: AlertDeliveryStatus
    message_id: str


class AlertPublisher(Protocol):
    @property
    def provider_name(self) -> str:
        """Stable alert-provider identifier."""

    async def publish(
        self,
        event: AlertEvent,
    ) -> AlertPublishResult:
        """Publish or safely simulate a human alert."""

    async def health(
        self,
    ) -> dict[str, object]:
        """Return provider health without requiring a network probe."""
