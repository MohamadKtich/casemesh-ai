from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

import casemesh.services.actions as actions_module
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
            findings_text="Synthetic grounded finding.",
            assessment_text="Synthetic assessment.",
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
    def __init__(self) -> None:
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


@asynccontextmanager
async def fake_open_checkpointer(
    settings: Settings,
) -> AsyncIterator[object]:
    del settings

    yield object()


def _service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    metadata_json: dict[str, object] | None = None,
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

    action_repository = FakeActionRepository()

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
        action_repository=(action_repository),
        policy_guard=PolicyGuard(
            allow_internal_note_without_review=True,
        ),
    )

    return (
        service,
        action_repository,
    )


def _policy_audit(
    repository: FakeActionRepository,
) -> dict[str, object]:
    matches = [
        event for event in repository.audit_events if event["event_type"] == "policy_evaluated"
    ]

    assert len(matches) == 1

    details = matches[0]["details"]

    assert isinstance(
        details,
        dict,
    )

    return details


def _trigger_details(
    repository: FakeActionRepository,
) -> dict[str, object]:
    details = _policy_audit(repository)

    raw = details.get("action_risk_triggers")

    assert isinstance(
        raw,
        dict,
    )

    return raw


@pytest.mark.asyncio
async def test_safe_internal_note_has_no_action_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository = _service(monkeypatch)

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type="create_internal_note",
        payload={
            "note": "Synthetic note.",
        },
    )

    assert result.status == ("auto_approved")

    assert result.policy.decision == ("allow")

    assert result.policy.requires_human_approval is False

    trigger_details = _trigger_details(repository)

    assert trigger_details["human_review_signal"] is False

    assert trigger_details["reason_codes"] == []

    assert trigger_details["triggers"] == []

    assert trigger_details["bedrock_action_review_performed"] is False


@pytest.mark.asyncio
async def test_high_risk_notification_records_trigger_and_requires_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository = _service(monkeypatch)

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type=("send_customer_notification"),
        payload={
            "message": "Synthetic message.",
        },
    )

    assert result.status == ("awaiting_approval")

    assert result.policy.decision == ("require_approval")

    assert result.policy.risk_level == ("high")

    assert result.policy.requires_human_approval is True

    trigger_details = _trigger_details(repository)

    assert trigger_details["human_review_signal"] is True

    assert trigger_details["reason_codes"] == [
        "HIGH_RISK_ACTION",
    ]

    triggers = trigger_details["triggers"]

    assert isinstance(
        triggers,
        list,
    )

    assert triggers[0]["source"] == "action"

    assert trigger_details["bedrock_action_review_performed"] is False


@pytest.mark.asyncio
async def test_financial_action_records_both_action_triggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository = _service(monkeypatch)

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type="issue_sla_credit",
        payload={
            "credit_percent": 10,
        },
    )

    assert result.status == ("awaiting_approval")

    assert result.policy.decision == ("require_approval")

    assert result.policy.risk_level == ("critical")

    assert result.policy.requires_human_approval is True

    trigger_details = _trigger_details(repository)

    assert trigger_details["reason_codes"] == [
        "HIGH_RISK_ACTION",
        "FINANCIAL_ACTION",
    ]

    assert trigger_details["human_review_signal"] is True

    assert trigger_details["bedrock_action_review_performed"] is False


@pytest.mark.asyncio
async def test_blocked_action_stays_blocked_even_when_triggered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository = _service(monkeypatch)

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type="unknown_action",
        payload={},
    )

    assert result.status == ("blocked")

    assert result.policy.decision == ("block")

    assert result.policy.risk_level == ("high")

    assert result.policy.requires_human_approval is False

    trigger_details = _trigger_details(repository)

    assert trigger_details["reason_codes"] == [
        "HIGH_RISK_ACTION",
    ]

    assert trigger_details["human_review_signal"] is True

    event_types = [event["event_type"] for event in repository.audit_events]

    assert event_types == [
        "policy_evaluated",
        "action_blocked",
    ]


@pytest.mark.asyncio
async def test_action_trigger_audit_does_not_claim_bedrock_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository = _service(monkeypatch)

    await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type="issue_sla_credit",
        payload={
            "credit_percent": 10,
        },
    )

    trigger_details = _trigger_details(repository)

    assert trigger_details["bedrock_action_review_performed"] is False

    assert "second_review" not in (trigger_details)


@pytest.mark.asyncio
async def test_completed_continue_second_review_does_not_remove_action_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository = _service(
        monkeypatch,
        metadata_json={
            "second_review": {
                "status": "completed",
                "effective_route": "continue",
            }
        },
    )

    result = await service.propose(
        case_id=CASE_ID,
        workflow_id=RUN_ID,
        action_type=("send_customer_notification"),
        payload={
            "message": "Synthetic message.",
        },
    )

    assert result.policy.decision == ("require_approval")

    assert _trigger_details(repository)["reason_codes"] == [
        "HIGH_RISK_ACTION",
    ]
