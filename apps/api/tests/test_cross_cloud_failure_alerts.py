from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest

from casemesh.alerts import (
    AlertDispatcher,
    AlertEvent,
    AlertPublishResult,
)
from casemesh.core.config import (
    Settings,
)
from casemesh.intelligence import (
    SecondReviewRequest,
    SecondReviewResult,
)
from casemesh.intelligence.guarded_review import (
    SecondReviewGuardrailFailureError,
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


class FakeRepository:
    def __init__(
        self,
    ) -> None:
        self.saved = 0
        self.snapshots: list[dict[str, object]] = []

    async def save(
        self,
        run: object,
    ) -> object:
        self.saved += 1

        metadata = run.metadata_json

        assert isinstance(
            metadata,
            dict,
        )

        self.snapshots.append(deepcopy(metadata))

        return run


class RecordingPublisher:
    provider_name = "synthetic-alert-recorder"

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
            message_id=("synthetic-alert-id"),
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "network_checked": False,
        }


class AWSFailingReviewer:
    provider_name = "aws-bedrock"
    model_name = "synthetic-model"

    def __init__(
        self,
    ) -> None:
        self.calls = 0

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        del request

        self.calls += 1

        raise RuntimeError("synthetic Bedrock outage")

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class AWSGuardrailFailingReviewer:
    provider_name = "aws-bedrock"
    model_name = "synthetic-model"

    def __init__(
        self,
    ) -> None:
        self.calls = 0

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        del request

        self.calls += 1

        raise SecondReviewGuardrailFailureError(
            stage="input",
            error_type=("BedrockGuardrailTimeoutError"),
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class SyntheticFailingReviewer:
    provider_name = "synthetic-reviewer"

    model_name = "synthetic-model"

    def __init__(
        self,
    ) -> None:
        self.calls = 0

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        del request

        self.calls += 1

        raise RuntimeError("synthetic non-AWS outage")

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


def _state() -> InvestigationState:
    return {
        "workflow_id": RUN_ID,
        "case_id": CASE_ID,
        "objective": ("Evaluate synthetic evidence."),
        "findings": ("Synthetic finding [E1]."),
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


def _settings(
    *,
    guardrails: bool = False,
) -> Settings:
    kwargs: dict[
        str,
        object,
    ] = {
        "_env_file": None,
        "aws_intelligence_enabled": True,
        "aws_client_mode": "sdk",
        "aws_bedrock_review_enabled": True,
        "aws_bedrock_model_id": ("synthetic-model"),
        "aws_max_reviews_per_investigation": 1,
    }

    if guardrails:
        kwargs.update(
            {
                "aws_bedrock_guardrails_enabled": True,
                "aws_bedrock_guardrail_id": ("synthetic-guardrail"),
                "aws_bedrock_guardrail_version": ("1"),
            }
        )

    return Settings(
        **kwargs,
    )


def _workflow(
    *,
    reviewer: object | None,
    metadata: dict[
        str,
        object,
    ]
    | None = None,
    guardrails: bool = False,
) -> tuple[
    InvestigationWorkflow,
    SimpleNamespace,
    FakeRepository,
    RecordingPublisher,
]:
    run = SimpleNamespace(
        id=RUN_ID,
        current_step=("evaluate_risk_triggers"),
        metadata_json=(deepcopy(metadata) if metadata is not None else {}),
    )

    repository = FakeRepository()
    publisher = RecordingPublisher()

    workflow = InvestigationWorkflow(
        run=run,
        settings=_settings(
            guardrails=guardrails,
        ),
        case_reader=object(),
        investigation_repository=(repository),
        retrieval_service=object(),
        answer_service=object(),
        second_review_provider=(reviewer),
        alert_dispatcher=AlertDispatcher(publisher),
    )

    return (
        workflow,
        run,
        repository,
        publisher,
    )


@pytest.mark.asyncio
async def test_real_bedrock_provider_failure_emits_cross_cloud_failure() -> None:
    reviewer = AWSFailingReviewer()

    (
        workflow,
        run,
        repository,
        publisher,
    ) = _workflow(
        reviewer=reviewer,
    )

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert reviewer.calls == 1

    assert outcome["status"] == "failed"

    assert outcome["aws_boundary_failure"] is True

    assert outcome["aws_boundary_component"] == "bedrock_review"

    assert outcome["effective_route"] == "human_review"

    assert len(publisher.events) == 1

    event = publisher.events[0]

    assert event.event_type == ("CROSS_CLOUD_FAILURE")

    assert event.source == ("aws_boundary")

    assert event.severity == "high"

    assert event.case_id == CASE_ID

    assert event.investigation_run_id == (RUN_ID)

    assert event.reason_codes == (
        "aws_boundary_failure",
        "provider_failure",
    )

    assert event.status == "failed"

    payload = event.payload()

    assert "error_type" not in payload
    assert "provider" not in payload
    assert "model" not in payload
    assert "rationale" not in payload

    assert repository.saved == 2

    assert run.metadata_json["second_review"]["aws_boundary_failure"] is True


@pytest.mark.asyncio
async def test_real_bedrock_guardrail_failure_emits_cross_cloud_failure() -> None:
    reviewer = AWSGuardrailFailingReviewer()

    (
        workflow,
        _,
        _,
        publisher,
    ) = _workflow(
        reviewer=reviewer,
        guardrails=True,
    )

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert reviewer.calls == 1

    assert outcome["status"] == "guardrail_failed"

    assert outcome["aws_boundary_failure"] is True

    assert outcome["aws_boundary_component"] == "bedrock_guardrails"

    assert len(publisher.events) == 1

    event = publisher.events[0]

    assert event.event_type == ("CROSS_CLOUD_FAILURE")

    assert event.reason_codes == (
        "aws_boundary_failure",
        "guardrail_failure",
    )

    assert event.status == ("guardrail_failed")


@pytest.mark.asyncio
async def test_synthetic_provider_failure_is_not_cross_cloud_failure() -> None:
    reviewer = SyntheticFailingReviewer()

    (
        workflow,
        _,
        _,
        publisher,
    ) = _workflow(
        reviewer=reviewer,
    )

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert outcome["status"] == "failed"

    assert "aws_boundary_failure" not in outcome

    assert publisher.events == []


@pytest.mark.asyncio
async def test_local_request_validation_failure_is_not_cross_cloud_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewer = AWSFailingReviewer()

    (
        workflow,
        _,
        repository,
        publisher,
    ) = _workflow(
        reviewer=reviewer,
    )

    def fail_request(
        self: InvestigationWorkflow,
        state: InvestigationState,
    ) -> SecondReviewRequest:
        del self
        del state

        raise ValueError("synthetic local request failure")

    monkeypatch.setattr(
        InvestigationWorkflow,
        "_build_second_review_request",
        fail_request,
    )

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert reviewer.calls == 0

    assert outcome["status"] == "failed"

    assert "aws_boundary_failure" not in outcome

    assert publisher.events == []

    # No external attempt was reserved.
    assert repository.saved == 1


@pytest.mark.asyncio
async def test_provider_unavailable_is_not_cross_cloud_failure() -> None:
    (
        workflow,
        _,
        repository,
        publisher,
    ) = _workflow(
        reviewer=None,
    )

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert outcome["status"] == "unavailable"

    assert "aws_boundary_failure" not in outcome

    assert publisher.events == []

    assert repository.saved == 1


@pytest.mark.asyncio
async def test_budget_exhaustion_is_not_cross_cloud_failure() -> None:
    reviewer = AWSFailingReviewer()

    (
        workflow,
        _,
        repository,
        publisher,
    ) = _workflow(
        reviewer=reviewer,
        metadata={
            "second_review_budget": {
                "reserved_attempts": 1,
                "max_reviews": 1,
            }
        },
    )

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert reviewer.calls == 0

    assert outcome["status"] == "budget_exhausted"

    assert "aws_boundary_failure" not in outcome

    assert publisher.events == []

    assert repository.saved == 1


@pytest.mark.asyncio
async def test_cross_cloud_failure_replay_does_not_reemit_alert() -> None:
    reviewer = AWSFailingReviewer()

    (
        workflow,
        _,
        repository,
        publisher,
    ) = _workflow(
        reviewer=reviewer,
    )

    first = await workflow._second_review(_state())

    first_save_count = repository.saved

    second = await workflow._second_review(_state())

    assert reviewer.calls == 1

    assert len(publisher.events) == 1

    assert repository.saved == (first_save_count)

    assert first["second_review"] == second["second_review"]


class FailingAlertPublisher:
    provider_name = "synthetic-failing-alert-publisher"

    def __init__(
        self,
    ) -> None:
        self.calls = 0
        self.events: list[AlertEvent] = []

    async def publish(
        self,
        event: AlertEvent,
    ) -> AlertPublishResult:
        self.calls += 1

        self.events.append(event)

        raise RuntimeError("synthetic SNS transport outage")

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "network_checked": False,
        }


@pytest.mark.asyncio
async def test_bedrock_failure_and_alert_failure_preserve_case_outcome() -> None:
    run = SimpleNamespace(
        id=RUN_ID,
        current_step=("evaluate_risk_triggers"),
        metadata_json={
            "existing": "preserved",
        },
    )

    repository = FakeRepository()
    reviewer = AWSFailingReviewer()
    publisher = FailingAlertPublisher()

    workflow = InvestigationWorkflow(
        run=run,
        settings=_settings(),
        case_reader=object(),
        investigation_repository=(repository),
        retrieval_service=object(),
        answer_service=object(),
        second_review_provider=(reviewer),
        alert_dispatcher=AlertDispatcher(publisher),
    )

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    # ------------------------------------------------------------
    # Bedrock failure remains authoritative review outcome.
    # ------------------------------------------------------------

    assert reviewer.calls == 1

    assert outcome["status"] == "failed"

    assert outcome["effective_route"] == "human_review"

    assert outcome["forced_human_review"] is True

    assert outcome["reason_codes"] == [
        "provider_failure",
    ]

    assert outcome["aws_boundary_failure"] is True

    assert outcome["aws_boundary_component"] == "bedrock_review"

    assert outcome["error_type"] == "RuntimeError"

    # ------------------------------------------------------------
    # CROSS_CLOUD_FAILURE was attempted exactly once.
    # ------------------------------------------------------------

    assert publisher.calls == 1

    assert len(publisher.events) == 1

    alert = publisher.events[0]

    assert alert.event_type == ("CROSS_CLOUD_FAILURE")

    assert alert.source == ("aws_boundary")

    assert alert.severity == "high"

    assert alert.reason_codes == (
        "aws_boundary_failure",
        "provider_failure",
    )

    # ------------------------------------------------------------
    # SNS failure is advisory metadata only.
    # ------------------------------------------------------------

    delivery = outcome["alert_delivery"]

    assert isinstance(
        delivery,
        dict,
    )

    assert delivery["event_type"] == "CROSS_CLOUD_FAILURE"

    assert delivery["status"] == "failed"

    assert delivery["attempted"] is True

    assert delivery["delivered"] is False

    assert delivery["provider"] == ("synthetic-failing-alert-publisher")

    assert delivery["error_type"] == "RuntimeError"

    assert "message_id" not in delivery

    # ------------------------------------------------------------
    # Investigation state is still persisted.
    # First save = review attempt reservation.
    # Second save = final failed outcome + alert failure metadata.
    # ------------------------------------------------------------

    assert repository.saved == 2

    assert len(repository.snapshots) == 2

    final_snapshot = repository.snapshots[-1]

    assert final_snapshot["existing"] == "preserved"

    persisted = final_snapshot["second_review"]

    assert isinstance(
        persisted,
        dict,
    )

    assert persisted["status"] == "failed"

    assert persisted["effective_route"] == "human_review"

    assert persisted["aws_boundary_failure"] is True

    assert persisted["alert_delivery"]["status"] == "failed"

    # ------------------------------------------------------------
    # Raw infrastructure messages never persist.
    # ------------------------------------------------------------

    serialized_metadata = repr(run.metadata_json)

    assert "synthetic Bedrock outage" not in serialized_metadata

    assert "synthetic SNS transport outage" not in serialized_metadata


@pytest.mark.asyncio
async def test_bedrock_and_sns_failure_replay_does_not_retry_either_boundary() -> None:
    run = SimpleNamespace(
        id=RUN_ID,
        current_step=("evaluate_risk_triggers"),
        metadata_json={},
    )

    repository = FakeRepository()
    reviewer = AWSFailingReviewer()
    publisher = FailingAlertPublisher()

    workflow = InvestigationWorkflow(
        run=run,
        settings=_settings(),
        case_reader=object(),
        investigation_repository=(repository),
        retrieval_service=object(),
        answer_service=object(),
        second_review_provider=(reviewer),
        alert_dispatcher=AlertDispatcher(publisher),
    )

    first = await workflow._second_review(_state())

    save_count = repository.saved

    second = await workflow._second_review(_state())

    assert reviewer.calls == 1

    assert publisher.calls == 1

    assert len(publisher.events) == 1

    assert repository.saved == (save_count)

    assert first["second_review"] == second["second_review"]

    assert second["second_review"]["alert_delivery"]["status"] == "failed"


@pytest.mark.asyncio
async def test_guardrail_failure_and_alert_failure_are_both_isolated() -> None:
    run = SimpleNamespace(
        id=RUN_ID,
        current_step=("evaluate_risk_triggers"),
        metadata_json={},
    )

    repository = FakeRepository()

    reviewer = AWSGuardrailFailingReviewer()

    publisher = FailingAlertPublisher()

    workflow = InvestigationWorkflow(
        run=run,
        settings=_settings(
            guardrails=True,
        ),
        case_reader=object(),
        investigation_repository=(repository),
        retrieval_service=object(),
        answer_service=object(),
        second_review_provider=(reviewer),
        alert_dispatcher=AlertDispatcher(publisher),
    )

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert reviewer.calls == 1
    assert publisher.calls == 1

    assert outcome["status"] == "guardrail_failed"

    assert outcome["effective_route"] == "human_review"

    assert outcome["forced_human_review"] is True

    assert outcome["aws_boundary_failure"] is True

    assert outcome["aws_boundary_component"] == "bedrock_guardrails"

    assert outcome["alert_delivery"]["status"] == "failed"

    assert repository.saved == 2


@pytest.mark.asyncio
async def test_alert_failure_does_not_create_recursive_cross_cloud_failure() -> None:
    run = SimpleNamespace(
        id=RUN_ID,
        current_step=("evaluate_risk_triggers"),
        metadata_json={},
    )

    repository = FakeRepository()
    reviewer = AWSFailingReviewer()
    publisher = FailingAlertPublisher()

    workflow = InvestigationWorkflow(
        run=run,
        settings=_settings(),
        case_reader=object(),
        investigation_repository=(repository),
        retrieval_service=object(),
        answer_service=object(),
        second_review_provider=(reviewer),
        alert_dispatcher=AlertDispatcher(publisher),
    )

    await workflow._second_review(_state())

    # One Bedrock boundary failure causes one alert attempt.
    # The alert transport failure does not produce another alert.
    assert reviewer.calls == 1

    assert publisher.calls == 1

    assert [event.event_type for event in publisher.events] == [
        "CROSS_CLOUD_FAILURE",
    ]
