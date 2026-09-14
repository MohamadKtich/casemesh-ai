from types import SimpleNamespace
from uuid import UUID

import pytest

from casemesh.alerts import (
    AlertDispatcher,
    AlertEvent,
    AlertPublishResult,
)
from casemesh.core.config import Settings
from casemesh.intelligence import (
    GuardrailAssessment,
    SecondReviewRequest,
    SecondReviewResult,
)
from casemesh.intelligence.guarded_review import (
    SecondReviewGuardrailBlockedError,
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


class FakeInvestigationRepository:
    def __init__(
        self,
    ) -> None:
        self.saved = 0

    async def save(
        self,
        run: object,
    ) -> object:
        self.saved += 1
        return run


class RecordingAlertPublisher:
    provider_name = "recording-alert-provider"

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
            message_id="synthetic-alert-id",
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class FailingAlertPublisher:
    provider_name = "failing-alert-provider"

    async def publish(
        self,
        event: AlertEvent,
    ) -> AlertPublishResult:
        del event

        raise RuntimeError("raw synthetic SNS transport detail")

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class SyntheticReviewer:
    provider_name = "synthetic-reviewer"
    model_name = "synthetic-model"

    def __init__(
        self,
        *,
        agreement: str = "agree",
        risk_level: str = "low",
        route: str = "continue",
    ) -> None:
        self._agreement = agreement
        self._risk_level = risk_level
        self._route = route

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        del request

        return SecondReviewResult(
            provider=self.provider_name,
            model=self.model_name,
            agreement=self._agreement,  # type: ignore[arg-type]
            risk_level=self._risk_level,  # type: ignore[arg-type]
            concerns=(),
            recommended_route=self._route,  # type: ignore[arg-type]
            rationale="Synthetic rationale.",
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class GuardrailBlockingReviewer:
    provider_name = "synthetic-reviewer"
    model_name = "synthetic-model"

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        del request

        raise SecondReviewGuardrailBlockedError(
            GuardrailAssessment(
                provider="synthetic-guardrail",
                stage="input",
                decision="block",
                reason_codes=("SYNTHETIC_BLOCK",),
                message=None,
            )
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class GuardrailFailingReviewer:
    provider_name = "synthetic-reviewer"
    model_name = "synthetic-model"

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        del request

        raise SecondReviewGuardrailFailureError(
            stage="input",
            error_type="RuntimeError",
        )

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
        "objective": ("Synthetic investigation objective."),
        "findings": ("Synthetic supported finding."),
        "findings_confidence": "medium",
        "findings_abstained": False,
        "citations": [],
        "gaps": [],
        "second_review_requested": True,
    }


def _workflow(
    *,
    reviewer: object,
    dispatcher: AlertDispatcher,
) -> tuple[
    InvestigationWorkflow,
    SimpleNamespace,
    FakeInvestigationRepository,
]:
    run = SimpleNamespace(
        id=RUN_ID,
        current_step="evaluate_risk_triggers",
        metadata_json={
            "existing": "preserved",
        },
    )

    repository = FakeInvestigationRepository()

    workflow = InvestigationWorkflow(
        run=run,
        settings=Settings(
            _env_file=None,
        ),
        case_reader=object(),
        investigation_repository=repository,
        retrieval_service=object(),
        answer_service=object(),
        second_review_provider=reviewer,
        alert_dispatcher=dispatcher,
    )

    return (
        workflow,
        run,
        repository,
    )


def _second_review_outcome(
    update: InvestigationState,
) -> dict[str, object]:
    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    return outcome


@pytest.mark.asyncio
async def test_disagreement_emits_second_review_disagreement_alert() -> None:
    publisher = RecordingAlertPublisher()

    workflow, run, repository = _workflow(
        reviewer=SyntheticReviewer(
            agreement="disagree",
            risk_level="high",
            route="human_review",
        ),
        dispatcher=AlertDispatcher(publisher),
    )

    update = await workflow._second_review(_state())

    outcome = _second_review_outcome(update)

    assert outcome["status"] == "completed"

    assert len(publisher.events) == 1

    event = publisher.events[0]

    assert event.event_type == ("SECOND_REVIEW_DISAGREEMENT")

    assert event.severity == "high"
    assert event.source == "second_review"
    assert event.case_id == CASE_ID

    assert event.investigation_run_id == (RUN_ID)

    assert "review_disagreed" in (event.reason_codes)

    delivery = outcome["alert_delivery"]

    assert isinstance(
        delivery,
        dict,
    )

    assert delivery["status"] == "published"

    assert delivery["delivered"] is True

    assert delivery["message_id"] == "synthetic-alert-id"

    assert run.metadata_json["existing"] == "preserved"

    assert run.metadata_json["second_review"] == outcome

    assert repository.saved == 1


@pytest.mark.asyncio
async def test_critical_disagreement_emits_critical_alert() -> None:
    publisher = RecordingAlertPublisher()

    workflow, _, _ = _workflow(
        reviewer=SyntheticReviewer(
            agreement="disagree",
            risk_level="critical",
            route="human_review",
        ),
        dispatcher=AlertDispatcher(publisher),
    )

    await workflow._second_review(_state())

    assert len(publisher.events) == 1

    assert publisher.events[0].severity == "critical"


@pytest.mark.asyncio
async def test_agreement_does_not_emit_disagreement_alert() -> None:
    publisher = RecordingAlertPublisher()

    workflow, _, _ = _workflow(
        reviewer=SyntheticReviewer(
            agreement="agree",
            risk_level="low",
            route="continue",
        ),
        dispatcher=AlertDispatcher(publisher),
    )

    update = await workflow._second_review(_state())

    outcome = _second_review_outcome(update)

    assert outcome["status"] == "completed"

    assert publisher.events == []

    assert "alert_delivery" not in (outcome)


@pytest.mark.asyncio
async def test_uncertain_review_does_not_emit_disagreement_alert() -> None:
    publisher = RecordingAlertPublisher()

    workflow, _, _ = _workflow(
        reviewer=SyntheticReviewer(
            agreement="uncertain",
            risk_level="medium",
            route="human_review",
        ),
        dispatcher=AlertDispatcher(publisher),
    )

    update = await workflow._second_review(_state())

    outcome = _second_review_outcome(update)

    assert outcome["status"] == "completed"

    assert "review_uncertain" in (outcome["reason_codes"])

    assert "review_disagreed" not in (outcome["reason_codes"])

    assert publisher.events == []

    assert "alert_delivery" not in (outcome)


@pytest.mark.asyncio
async def test_guardrail_block_emits_guardrail_block_alert() -> None:
    publisher = RecordingAlertPublisher()

    workflow, _, _ = _workflow(
        reviewer=GuardrailBlockingReviewer(),
        dispatcher=AlertDispatcher(publisher),
    )

    update = await workflow._second_review(_state())

    outcome = _second_review_outcome(update)

    assert outcome["status"] == "guardrail_blocked"

    assert len(publisher.events) == 1

    event = publisher.events[0]

    assert event.event_type == ("GUARDRAIL_BLOCK")

    assert event.severity == "critical"
    assert event.source == "guardrail"

    assert "guardrail_blocked" in (event.reason_codes)

    assert "SYNTHETIC_BLOCK" in (event.reason_codes)

    delivery = outcome["alert_delivery"]

    assert isinstance(
        delivery,
        dict,
    )

    assert delivery["delivered"] is True


@pytest.mark.asyncio
async def test_guardrail_failure_is_not_reported_as_guardrail_block() -> None:
    publisher = RecordingAlertPublisher()

    workflow, _, _ = _workflow(
        reviewer=GuardrailFailingReviewer(),
        dispatcher=AlertDispatcher(publisher),
    )

    update = await workflow._second_review(_state())

    outcome = _second_review_outcome(update)

    assert outcome["status"] == "guardrail_failed"

    assert outcome["reason_codes"] == [
        "guardrail_failure",
    ]

    assert publisher.events == []

    assert "alert_delivery" not in (outcome)


@pytest.mark.asyncio
async def test_alert_transport_failure_does_not_fail_second_review() -> None:
    workflow, run, repository = _workflow(
        reviewer=SyntheticReviewer(
            agreement="disagree",
            risk_level="high",
            route="human_review",
        ),
        dispatcher=AlertDispatcher(FailingAlertPublisher()),
    )

    update = await workflow._second_review(_state())

    outcome = _second_review_outcome(update)

    assert outcome["status"] == "completed"

    assert outcome["effective_route"] == "human_review"

    delivery = outcome["alert_delivery"]

    assert isinstance(
        delivery,
        dict,
    )

    assert delivery["status"] == "failed"

    assert delivery["attempted"] is True

    assert delivery["delivered"] is False

    assert delivery["error_type"] == "RuntimeError"

    assert "raw synthetic SNS transport detail" not in repr(outcome)

    assert run.metadata_json["second_review"] == outcome

    assert repository.saved == 1


@pytest.mark.asyncio
async def test_disabled_alerting_records_disabled_delivery_for_real_event() -> None:
    workflow, _, _ = _workflow(
        reviewer=SyntheticReviewer(
            agreement="disagree",
            risk_level="high",
            route="human_review",
        ),
        dispatcher=AlertDispatcher(None),
    )

    update = await workflow._second_review(_state())

    outcome = _second_review_outcome(update)

    delivery = outcome["alert_delivery"]

    assert isinstance(
        delivery,
        dict,
    )

    assert delivery["status"] == "disabled"

    assert delivery["attempted"] is False

    assert delivery["delivered"] is False
