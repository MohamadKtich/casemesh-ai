from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

import casemesh.services.actions as actions_module
from casemesh.alerts import (
    AlertDispatcher,
    AlertEvent,
    AlertPublishResult,
)
from casemesh.core.config import Settings
from casemesh.policy.guardrails import PolicyGuard
from casemesh.services.actions import ActionService

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")

RUN_ID = UUID("22222222-2222-2222-2222-222222222222")

ACTION_ID = UUID("33333333-3333-3333-3333-333333333333")

APPROVAL_ID = UUID("44444444-4444-4444-4444-444444444444")

RESOLUTION_ID = UUID("55555555-5555-5555-5555-555555555555")


class FakeCaseRepository:
    async def get(
        self,
        case_id: UUID,
    ) -> object | None:
        assert case_id == CASE_ID
        return object()


class FakeInvestigationRepository:
    def __init__(
        self,
        *,
        metadata_json: dict[str, object] | None = None,
    ) -> None:
        self.investigation = SimpleNamespace(
            id=RUN_ID,
            state="completed",
            confidence="high",
            abstained=False,
            citations_json=[
                {
                    "citation": "synthetic",
                }
            ],
            metadata_json=(metadata_json if metadata_json is not None else {}),
            findings_text=("Synthetic grounded finding."),
            assessment_text=("Synthetic assessment."),
        )

    async def get_for_case(
        self,
        *,
        case_id: UUID,
        workflow_id: UUID,
    ) -> object | None:
        assert case_id == CASE_ID
        assert workflow_id == RUN_ID

        return self.investigation


class FakeActionRepository:
    def __init__(
        self,
    ) -> None:
        self.audit_events: list[dict[str, object]] = []

        self.created_action: SimpleNamespace | None = None

        self.created_approval: SimpleNamespace | None = None

    async def create(
        self,
        *,
        case_id: UUID,
        investigation: object,
        action_type: str,
        payload: dict[str, object],
        policy_decision: str,
        policy_rationale: str,
        risk_level: str,
        requires_human_approval: bool,
    ) -> tuple[
        SimpleNamespace,
        SimpleNamespace | None,
    ]:
        del investigation

        now = datetime.now(UTC)

        approval = None

        if requires_human_approval:
            approval = SimpleNamespace(
                id=APPROVAL_ID,
                decision="pending",
                reviewer_ref=None,
                comment=None,
            )

        action = SimpleNamespace(
            id=ACTION_ID,
            case_id=case_id,
            investigation_run_id=RUN_ID,
            resolution_draft_id=RESOLUTION_ID,
            approval_id=(APPROVAL_ID if approval is not None else None),
            thread_id=f"action:{ACTION_ID}",
            action_type=action_type,
            status="pending",
            policy_decision=policy_decision,
            policy_rationale=policy_rationale,
            risk_level=risk_level,
            requires_human_approval=(requires_human_approval),
            payload_json=payload,
            reviewed_payload_json=payload,
            error_message=None,
            created_at=now,
            updated_at=now,
        )

        self.created_action = action
        self.created_approval = approval

        return (
            action,
            approval,
        )

    async def save_action(
        self,
        action: SimpleNamespace,
    ) -> SimpleNamespace:
        self.created_action = action
        return action

    async def add_audit(
        self,
        *,
        case_id: UUID,
        investigation_run_id: UUID | None,
        action_request_id: UUID | None,
        actor_type: str,
        actor_ref: str | None,
        event_type: str,
        details: dict[str, object],
    ) -> object:
        event = {
            "case_id": case_id,
            "investigation_run_id": (investigation_run_id),
            "action_request_id": (action_request_id),
            "actor_type": actor_type,
            "actor_ref": actor_ref,
            "event_type": event_type,
            "details": details,
        }

        self.audit_events.append(event)

        return event


class FakeActionApprovalWorkflow:
    def __init__(
        self,
        *,
        checkpointer: object,
    ) -> None:
        self._checkpointer = checkpointer

    async def start(
        self,
        state: dict[str, object],
    ) -> dict[str, object]:
        if state["policy_decision"] == "allow":
            return {
                "status": "auto_approved",
            }

        return {
            "status": "pending",
            "__interrupt__": [
                "synthetic-interrupt",
            ],
        }

    @staticmethod
    def build_interrupt_payload(
        state: dict[str, object],
    ) -> dict[str, object]:
        return {
            "question": state["interrupt_question"],
            "action_type": state["action_type"],
        }


class RecordingAlertPublisher:
    provider_name = "recording-action-alert-provider"

    def __init__(
        self,
    ) -> None:
        self.events: list[AlertEvent] = []

    async def publish(
        self,
        event: AlertEvent,
    ) -> AlertPublishResult:
        self.events.append(event)

        return AlertPublishResult(
            provider=self.provider_name,
            event_type=event.event_type,
            delivery_status="published",
            message_id=("synthetic-action-alert-id"),
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class FailingAlertPublisher:
    provider_name = "failing-action-alert-provider"

    async def publish(
        self,
        event: AlertEvent,
    ) -> AlertPublishResult:
        del event

        raise RuntimeError("raw synthetic SNS failure that must not affect approval")

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


@asynccontextmanager
async def fake_open_checkpointer(
    settings: Settings,
) -> AsyncIterator[object]:
    del settings

    yield object()


def _service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dispatcher: AlertDispatcher,
    metadata_json: dict[str, object] | None = None,
    allow_internal_note_without_review: bool = True,
) -> tuple[
    ActionService,
    FakeActionRepository,
]:
    monkeypatch.setattr(
        actions_module,
        "open_checkpointer",
        fake_open_checkpointer,
    )

    monkeypatch.setattr(
        actions_module,
        "ActionApprovalWorkflow",
        FakeActionApprovalWorkflow,
    )

    repository = FakeActionRepository()

    service = ActionService(
        settings=Settings(
            _env_file=None,
        ),
        case_repository=(FakeCaseRepository()),
        investigation_repository=(
            FakeInvestigationRepository(
                metadata_json=metadata_json,
            )
        ),
        action_repository=repository,
        policy_guard=PolicyGuard(
            allow_internal_note_without_review=(allow_internal_note_without_review),
        ),
        alert_dispatcher=dispatcher,
    )

    return (
        service,
        repository,
    )


def _audit_types(
    repository: FakeActionRepository,
) -> list[str]:
    return [str(event["event_type"]) for event in repository.audit_events]


@pytest.mark.asyncio
async def test_high_risk_approval_emits_approval_required_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = RecordingAlertPublisher()

    service, repository = _service(
        monkeypatch,
        dispatcher=AlertDispatcher(publisher),
    )

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type=("send_customer_notification"),
        payload={
            "message": ("Synthetic customer message."),
        },
    )

    assert result.status == ("awaiting_approval")

    assert result.policy.decision == ("require_approval")

    assert len(publisher.events) == 1

    event = publisher.events[0]

    assert event.event_type == ("APPROVAL_REQUIRED")

    assert event.severity == "high"
    assert event.source == "action"
    assert event.case_id == CASE_ID

    assert event.investigation_run_id == (RUN_ID)

    assert event.action_request_id == (ACTION_ID)

    assert event.reason_codes == ("HIGH_RISK_ACTION",)

    assert event.risk_level == "high"

    assert event.status == ("awaiting_approval")

    assert _audit_types(repository) == [
        "policy_evaluated",
        "approval_requested",
    ]

    forbidden = {
        "payload",
        "message",
        "findings",
        "evidence",
        "objective",
        "rationale",
    }

    assert forbidden.isdisjoint(event.payload())


@pytest.mark.asyncio
async def test_financial_approval_emits_critical_alert_with_both_triggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = RecordingAlertPublisher()

    service, _ = _service(
        monkeypatch,
        dispatcher=AlertDispatcher(publisher),
    )

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type="issue_sla_credit",
        payload={
            "credit_percent": 10,
        },
    )

    assert result.status == ("awaiting_approval")

    assert result.policy.risk_level == ("critical")

    assert len(publisher.events) == 1

    event = publisher.events[0]

    assert event.event_type == ("APPROVAL_REQUIRED")

    assert event.severity == ("critical")

    assert event.reason_codes == (
        "HIGH_RISK_ACTION",
        "FINANCIAL_ACTION",
    )

    assert event.risk_level == ("critical")


@pytest.mark.asyncio
async def test_second_review_forced_approval_has_explicit_reason_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = RecordingAlertPublisher()

    service, _ = _service(
        monkeypatch,
        dispatcher=AlertDispatcher(publisher),
        metadata_json={
            "second_review": {
                "status": "failed",
                "effective_route": ("human_review"),
            }
        },
    )

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type="create_internal_note",
        payload={
            "note": ("Synthetic internal note."),
        },
    )

    assert result.status == ("awaiting_approval")

    assert result.policy.decision == ("require_approval")

    assert len(publisher.events) == 1

    event = publisher.events[0]

    assert event.event_type == ("APPROVAL_REQUIRED")

    assert event.severity == ("warning")

    assert event.reason_codes == ("SECOND_REVIEW_REQUIRES_HUMAN",)

    assert event.risk_level == "low"


@pytest.mark.asyncio
async def test_policy_only_approval_has_fallback_reason_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = RecordingAlertPublisher()

    service, _ = _service(
        monkeypatch,
        dispatcher=AlertDispatcher(publisher),
        allow_internal_note_without_review=False,
    )

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type="create_internal_note",
        payload={
            "note": ("Synthetic policy-reviewed note."),
        },
    )

    assert result.status == ("awaiting_approval")

    assert len(publisher.events) == 1

    event = publisher.events[0]

    assert event.reason_codes == ("POLICY_REQUIRES_APPROVAL",)

    assert event.severity == ("warning")


@pytest.mark.asyncio
async def test_auto_approved_action_does_not_emit_approval_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = RecordingAlertPublisher()

    service, repository = _service(
        monkeypatch,
        dispatcher=AlertDispatcher(publisher),
    )

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type="create_internal_note",
        payload={
            "note": "Synthetic safe note.",
        },
    )

    assert result.status == ("auto_approved")

    assert publisher.events == []

    assert _audit_types(repository) == [
        "policy_evaluated",
        "action_auto_approved",
    ]


@pytest.mark.asyncio
async def test_blocked_action_does_not_emit_approval_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = RecordingAlertPublisher()

    service, repository = _service(
        monkeypatch,
        dispatcher=AlertDispatcher(publisher),
    )

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type="unknown_action",
        payload={},
    )

    assert result.status == "blocked"

    assert result.policy.decision == ("block")

    assert publisher.events == []

    assert _audit_types(repository) == [
        "policy_evaluated",
        "action_blocked",
    ]


@pytest.mark.asyncio
async def test_alert_transport_failure_does_not_change_approval_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository = _service(
        monkeypatch,
        dispatcher=AlertDispatcher(FailingAlertPublisher()),
    )

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type=("send_customer_notification"),
        payload={
            "message": ("Synthetic customer message."),
        },
    )

    assert result.status == ("awaiting_approval")

    assert result.policy.decision == ("require_approval")

    assert repository.created_action is not None

    assert repository.created_action.status == ("awaiting_approval")

    assert repository.created_action.error_message is None

    assert _audit_types(repository) == [
        "policy_evaluated",
        "approval_requested",
    ]

    serialized_audit = repr(repository.audit_events)

    assert "raw synthetic SNS failure" not in serialized_audit
