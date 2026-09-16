from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest

from casemesh.core.config import Settings
from casemesh.intelligence import (
    SecondReviewRequest,
    SecondReviewResult,
)
from casemesh.workflows.investigation import (
    InvestigationWorkflow,
)
from casemesh.workflows.state import (
    InvestigationState,
)

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")

RUN_ID = UUID("22222222-2222-2222-2222-222222222222")

CHUNK_ID = UUID("33333333-3333-3333-3333-333333333333")

DOCUMENT_ID = UUID("44444444-4444-4444-4444-444444444444")


class SnapshotRepository:
    def __init__(
        self,
    ) -> None:
        self.snapshots: list[dict[str, object]] = []

    async def save(
        self,
        run: object,
    ) -> object:
        metadata = run.metadata_json

        assert isinstance(
            metadata,
            dict,
        )

        self.snapshots.append(deepcopy(metadata))

        return run


class CountingReviewer:
    provider_name = "synthetic-reviewer"

    model_name = "synthetic-model"

    def __init__(
        self,
        *,
        repository: SnapshotRepository,
        error: Exception | None = None,
    ) -> None:
        self._repository = repository
        self._error = error
        self.calls = 0

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        del request

        self.calls += 1

        # Reservation must already be durable
        # before the external provider call.
        assert self._repository.snapshots

        latest = self._repository.snapshots[-1]

        budget = latest["second_review_budget"]

        assert isinstance(
            budget,
            dict,
        )

        assert budget["reserved_attempts"] >= 1

        assert "second_review" not in latest

        if self._error is not None:
            raise self._error

        return SecondReviewResult(
            provider=self.provider_name,
            model=self.model_name,
            agreement="agree",
            risk_level="low",
            concerns=(),
            recommended_route="continue",
            rationale=("Synthetic budget test."),
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": (self.provider_name),
            "network_checked": False,
        }


def _state() -> InvestigationState:
    return {
        "workflow_id": RUN_ID,
        "case_id": CASE_ID,
        "objective": ("Determine the supported conclusion."),
        "findings": ("Supported synthetic finding [E1]."),
        "findings_confidence": ("medium"),
        "findings_abstained": False,
        "citations": [
            {
                "label": "E1",
                "chunk_id": str(CHUNK_ID),
                "document_id": str(DOCUMENT_ID),
                "chunk_index": 0,
                "excerpt": ("Synthetic evidence."),
            }
        ],
        "gaps": [],
        "second_review_requested": True,
    }


def _workflow(
    *,
    max_reviews: int = 1,
    metadata: dict[
        str,
        object,
    ]
    | None = None,
    error: Exception | None = None,
) -> tuple[
    InvestigationWorkflow,
    SimpleNamespace,
    SnapshotRepository,
    CountingReviewer,
]:
    run = SimpleNamespace(
        id=RUN_ID,
        current_step="produce_findings",
        metadata_json=(
            deepcopy(metadata)
            if metadata is not None
            else {
                "existing": "preserved",
            }
        ),
    )

    repository = SnapshotRepository()

    reviewer = CountingReviewer(
        repository=repository,
        error=error,
    )

    workflow = InvestigationWorkflow(
        run=run,
        settings=Settings(
            _env_file=None,
            aws_max_reviews_per_investigation=(max_reviews),
        ),
        case_reader=object(),
        investigation_repository=(repository),
        retrieval_service=object(),
        answer_service=object(),
        second_review_provider=(reviewer),
    )

    return (
        workflow,
        run,
        repository,
        reviewer,
    )


@pytest.mark.asyncio
async def test_attempt_is_persisted_before_provider_call() -> None:
    (
        workflow,
        run,
        repository,
        reviewer,
    ) = _workflow()

    update = await workflow._second_review(_state())

    assert reviewer.calls == 1

    assert len(repository.snapshots) == 2

    reservation = repository.snapshots[0]

    assert reservation["second_review_budget"] == {
        "reserved_attempts": 1,
        "max_reviews": 1,
    }

    assert "second_review" not in reservation

    assert run.metadata_json["existing"] == "preserved"

    assert update["second_review"]["status"] == "completed"


@pytest.mark.asyncio
async def test_completed_review_replay_reuses_existing_outcome() -> None:
    (
        workflow,
        _,
        repository,
        reviewer,
    ) = _workflow()

    first = await workflow._second_review(_state())

    saves_after_first = len(repository.snapshots)

    second = await workflow._second_review(_state())

    assert reviewer.calls == 1

    assert len(repository.snapshots) == saves_after_first

    assert first["second_review"] == second["second_review"]


@pytest.mark.asyncio
async def test_exhausted_reserved_budget_fails_closed_without_provider_call() -> None:
    (
        workflow,
        _,
        repository,
        reviewer,
    ) = _workflow(
        metadata={
            "second_review_budget": {
                "reserved_attempts": 1,
                "max_reviews": 1,
            }
        }
    )

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert reviewer.calls == 0

    assert outcome["status"] == "budget_exhausted"

    assert outcome["effective_route"] == "human_review"

    assert outcome["forced_human_review"] is True

    assert outcome["reason_codes"] == [
        "review_budget_exhausted",
    ]

    assert outcome["reserved_attempts"] == 1

    assert outcome["max_reviews"] == 1

    assert len(repository.snapshots) == 1


@pytest.mark.asyncio
async def test_pre_reserved_attempt_can_recover_when_budget_allows_second_attempt() -> None:
    (
        workflow,
        run,
        repository,
        reviewer,
    ) = _workflow(
        max_reviews=2,
        metadata={
            "second_review_budget": {
                "reserved_attempts": 1,
                "max_reviews": 2,
            }
        },
    )

    update = await workflow._second_review(_state())

    assert reviewer.calls == 1

    assert run.metadata_json["second_review_budget"] == {
        "reserved_attempts": 2,
        "max_reviews": 2,
    }

    assert repository.snapshots[0]["second_review_budget"] == {
        "reserved_attempts": 2,
        "max_reviews": 2,
    }

    assert update["second_review"]["status"] == "completed"


@pytest.mark.asyncio
async def test_provider_failure_consumes_attempt_and_replay_does_not_call_again() -> None:
    (
        workflow,
        _,
        repository,
        reviewer,
    ) = _workflow(error=RuntimeError("synthetic provider outage"))

    first = await workflow._second_review(_state())

    assert reviewer.calls == 1

    assert first["second_review"]["status"] == "failed"

    assert repository.snapshots[0]["second_review_budget"]["reserved_attempts"] == 1

    saves_after_failure = len(repository.snapshots)

    second = await workflow._second_review(_state())

    assert reviewer.calls == 1

    assert len(repository.snapshots) == saves_after_failure

    assert first["second_review"] == second["second_review"]
