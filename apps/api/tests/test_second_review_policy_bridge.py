from types import SimpleNamespace
from uuid import UUID

import pytest

from casemesh.core.config import Settings
from casemesh.policy.guardrails import (
    PolicyEvaluation,
    PolicyGuard,
)
from casemesh.services.actions import (
    ActionService,
)

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")

RUN_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_second_review_escalates_allowed_internal_note() -> None:
    guard = PolicyGuard(
        allow_internal_note_without_review=True,
    )

    result = guard.evaluate(
        action_type="create_internal_note",
        payload={"note": "Synthetic note."},
        investigation_confidence="high",
        investigation_abstained=False,
        citation_count=1,
        second_review_requires_human=True,
    )

    assert result.decision == "require_approval"
    assert result.risk_level == "low"
    assert result.requires_human_approval is True

    assert "second-review gate" in result.rationale


def test_absent_second_review_preserves_internal_note_allow() -> None:
    guard = PolicyGuard(
        allow_internal_note_without_review=True,
    )

    result = guard.evaluate(
        action_type="create_internal_note",
        payload={"note": "Synthetic note."},
        investigation_confidence="high",
        investigation_abstained=False,
        citation_count=1,
    )

    assert result.decision == "allow"
    assert result.requires_human_approval is False


def test_second_review_never_downgrades_unknown_action_block() -> None:
    guard = PolicyGuard()

    result = guard.evaluate(
        action_type="delete_everything",
        payload={},
        investigation_confidence="high",
        investigation_abstained=False,
        citation_count=3,
        second_review_requires_human=True,
    )

    assert result.decision == "block"
    assert result.requires_human_approval is False


def test_second_review_never_downgrades_financial_block() -> None:
    guard = PolicyGuard()

    result = guard.evaluate(
        action_type="issue_sla_credit",
        payload={"credit_percent": 10},
        investigation_confidence="low",
        investigation_abstained=False,
        citation_count=1,
        second_review_requires_human=True,
    )

    assert result.decision == "block"
    assert result.risk_level == "critical"


@pytest.mark.parametrize(
    (
        "metadata",
        "expected",
    ),
    [
        (
            {},
            False,
        ),
        (
            {"unrelated": True},
            False,
        ),
        (
            {
                "second_review": {
                    "status": "completed",
                    "effective_route": "continue",
                }
            },
            False,
        ),
        (
            {
                "second_review": {
                    "status": "completed",
                    "effective_route": "human_review",
                }
            },
            True,
        ),
        (
            {
                "second_review": {
                    "status": "failed",
                    "effective_route": "human_review",
                }
            },
            True,
        ),
        (
            {
                "second_review": {
                    "status": "unavailable",
                    "effective_route": "human_review",
                }
            },
            True,
        ),
        (
            {
                "second_review": {
                    "status": "failed",
                    "effective_route": "continue",
                }
            },
            True,
        ),
        (
            {
                "second_review": {
                    "status": "completed",
                }
            },
            True,
        ),
        (
            {"second_review": "malformed"},
            True,
        ),
    ],
)
def test_second_review_metadata_is_interpreted_fail_closed(
    metadata: dict[str, object],
    expected: bool,
) -> None:
    assert ActionService._second_review_requires_human_review(metadata) is expected


class BridgeObserved(RuntimeError):
    pass


class FakeCaseRepository:
    async def get(
        self,
        case_id: UUID,
    ) -> object:
        assert case_id == CASE_ID
        return object()


class FakeInvestigationRepository:
    def __init__(
        self,
        *,
        metadata: dict[str, object],
    ) -> None:
        self.metadata = metadata

    async def get_for_case(
        self,
        *,
        case_id: UUID,
        workflow_id: UUID,
    ) -> object:
        assert case_id == CASE_ID
        assert workflow_id == RUN_ID

        return SimpleNamespace(
            id=RUN_ID,
            state="completed",
            confidence="high",
            abstained=False,
            citations_json=[{"label": "E1"}],
            metadata_json=self.metadata,
        )


class UnusedActionRepository:
    pass


class ProbePolicyGuard:
    def __init__(self) -> None:
        self.observed: bool | None = None

    def evaluate(
        self,
        *,
        action_type: str,
        payload: dict[str, object],
        investigation_confidence: str | None,
        investigation_abstained: bool,
        citation_count: int,
        second_review_requires_human: bool = False,
    ) -> PolicyEvaluation:
        _ = (
            action_type,
            payload,
            investigation_confidence,
            investigation_abstained,
            citation_count,
        )

        self.observed = second_review_requires_human

        raise BridgeObserved


@pytest.mark.parametrize(
    (
        "metadata",
        "expected",
    ),
    [
        (
            {},
            False,
        ),
        (
            {
                "second_review": {
                    "status": "completed",
                    "effective_route": "continue",
                }
            },
            False,
        ),
        (
            {
                "second_review": {
                    "status": "completed",
                    "effective_route": "human_review",
                }
            },
            True,
        ),
        (
            {
                "second_review": {
                    "status": "failed",
                    "effective_route": "human_review",
                }
            },
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_action_service_passes_review_signal_to_policy_guard(
    metadata: dict[str, object],
    expected: bool,
) -> None:
    policy = ProbePolicyGuard()

    service = ActionService(
        settings=Settings(),
        case_repository=FakeCaseRepository(),  # type: ignore[arg-type]
        investigation_repository=(FakeInvestigationRepository(metadata=metadata)),  # type: ignore[arg-type]
        action_repository=UnusedActionRepository(),  # type: ignore[arg-type]
        policy_guard=policy,  # type: ignore[arg-type]
    )

    with pytest.raises(BridgeObserved):
        await service.propose(
            case_id=CASE_ID,
            workflow_id=RUN_ID,
            action_type="create_internal_note",
            payload={"note": "Synthetic note."},
        )

    assert policy.observed is expected
