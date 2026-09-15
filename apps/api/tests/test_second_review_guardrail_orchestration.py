import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

import casemesh.workflows.investigation as investigation_module
from casemesh.api.routes.investigations import (
    build_second_review_provider,
)
from casemesh.core.config import Settings
from casemesh.integrations.aws.bedrock_review import (
    MockBedrockSecondReviewProvider,
)
from casemesh.intelligence.contracts import (
    GuardrailAssessment,
    SecondReviewRequest,
    SecondReviewResult,
)
from casemesh.intelligence.guarded_review import (
    GuardedSecondReviewProvider,
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
    def __init__(self) -> None:
        self.saved = 0

    async def save(
        self,
        run: object,
    ) -> object:
        self.saved += 1
        return run


class FakeReviewer:
    provider_name = "synthetic-reviewer"
    model_name = "synthetic-model"

    def __init__(
        self,
        *,
        events: list[str],
        result: SecondReviewResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.result = result
        self.error = error
        self.calls = 0

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        _ = request

        self.calls += 1
        self.events.append("review")

        if self.error is not None:
            raise self.error

        if self.result is None:
            raise AssertionError("Synthetic reviewer result was not configured.")

        return self.result

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class FakeGuardrail:
    provider_name = "synthetic-guardrail"

    def __init__(
        self,
        *,
        events: list[str],
        input_assessment: GuardrailAssessment | None = None,
        output_assessment: GuardrailAssessment | None = None,
        input_error: Exception | None = None,
        output_error: Exception | None = None,
    ) -> None:
        self.events = events

        self.input_assessment = input_assessment or _assessment(
            stage="input",
            decision="allow",
        )

        self.output_assessment = output_assessment or _assessment(
            stage="output",
            decision="allow",
        )

        self.input_error = input_error
        self.output_error = output_error

    async def assess_input(
        self,
        request: SecondReviewRequest,
    ) -> GuardrailAssessment:
        _ = request

        self.events.append("guardrail_input")

        if self.input_error is not None:
            raise self.input_error

        return self.input_assessment

    async def assess_output(
        self,
        *,
        request: SecondReviewRequest,
        result: SecondReviewResult,
    ) -> GuardrailAssessment:
        _ = (
            request,
            result,
        )

        self.events.append("guardrail_output")

        if self.output_error is not None:
            raise self.output_error

        return self.output_assessment

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


def _assessment(
    *,
    stage: str,
    decision: str,
    reason_codes: tuple[str, ...] = (),
) -> GuardrailAssessment:
    return GuardrailAssessment(
        provider="synthetic-guardrail",
        stage=stage,
        decision=decision,
        reason_codes=reason_codes,
        message=None,
    )


def _review_result(
    *,
    agreement: str = "agree",
    risk_level: str = "low",
    route: str = "continue",
) -> SecondReviewResult:
    return SecondReviewResult(
        provider="synthetic-reviewer",
        model="synthetic-model",
        agreement=agreement,
        risk_level=risk_level,
        concerns=(),
        recommended_route=route,
        rationale="Synthetic rationale.",
    )


def _state() -> InvestigationState:
    return {
        "workflow_id": RUN_ID,
        "case_id": CASE_ID,
        "objective": "Synthetic investigation objective.",
        "findings": "Synthetic supported finding.",
        "findings_confidence": "medium",
        "findings_abstained": False,
        "citations": [],
        "gaps": [],
        "second_review_requested": True,
    }


def _workflow(
    provider: object,
) -> tuple[
    InvestigationWorkflow,
    SimpleNamespace,
    FakeInvestigationRepository,
]:
    run = SimpleNamespace(
        id=RUN_ID,
        current_step="produce_findings",
        metadata_json={"existing_metadata": "preserved"},
    )

    repository = FakeInvestigationRepository()

    workflow = InvestigationWorkflow(
        run=run,
        settings=Settings(
            _env_file=None,
            aws_bedrock_review_enabled=False,
        ),
        case_reader=object(),
        investigation_repository=repository,
        retrieval_service=object(),
        answer_service=object(),
        second_review_provider=provider,
    )

    return (
        workflow,
        run,
        repository,
    )


@pytest.mark.asyncio
async def test_input_block_prevents_reviewer_and_decision_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    reviewer = FakeReviewer(
        events=events,
        result=_review_result(),
    )

    guardrail = FakeGuardrail(
        events=events,
        input_assessment=_assessment(
            stage="input",
            decision="block",
            reason_codes=("PROMPT_INJECTION_SIGNAL",),
        ),
    )

    provider = GuardedSecondReviewProvider(
        reviewer=reviewer,
        guardrail=guardrail,
    )

    def forbidden_gate(
        result: SecondReviewResult,
    ) -> object:
        _ = result
        raise AssertionError("Decision Gate must not run after input block.")

    monkeypatch.setattr(
        investigation_module,
        "evaluate_second_review",
        forbidden_gate,
    )

    workflow, run, repository = _workflow(provider)

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert events == ["guardrail_input"]

    assert reviewer.calls == 0

    assert outcome["status"] == "guardrail_blocked"

    assert outcome["guardrail_stage"] == "input"

    assert outcome["effective_route"] == "human_review"

    assert outcome["forced_human_review"] is True

    assert outcome["reason_codes"] == [
        "guardrail_blocked",
        "PROMPT_INJECTION_SIGNAL",
    ]

    assert repository.saved == 2
    assert run.current_step == "second_review"


@pytest.mark.asyncio
async def test_output_block_prevents_decision_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    reviewer = FakeReviewer(
        events=events,
        result=_review_result(),
    )

    guardrail = FakeGuardrail(
        events=events,
        output_assessment=_assessment(
            stage="output",
            decision="block",
            reason_codes=("GUARDRAIL_INTERVENED",),
        ),
    )

    provider = GuardedSecondReviewProvider(
        reviewer=reviewer,
        guardrail=guardrail,
    )

    def forbidden_gate(
        result: SecondReviewResult,
    ) -> object:
        _ = result
        raise AssertionError("Decision Gate must not run after output block.")

    monkeypatch.setattr(
        investigation_module,
        "evaluate_second_review",
        forbidden_gate,
    )

    workflow, _, repository = _workflow(provider)

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert events == [
        "guardrail_input",
        "review",
        "guardrail_output",
    ]

    assert reviewer.calls == 1

    assert outcome["status"] == "guardrail_blocked"

    assert outcome["guardrail_stage"] == "output"

    assert outcome["effective_route"] == "human_review"

    assert outcome["reason_codes"] == [
        "guardrail_blocked",
        "GUARDRAIL_INTERVENED",
    ]

    assert repository.saved == 2


@pytest.mark.asyncio
async def test_input_guardrail_failure_fails_closed_without_review() -> None:
    events: list[str] = []

    reviewer = FakeReviewer(
        events=events,
        result=_review_result(),
    )

    guardrail = FakeGuardrail(
        events=events,
        input_error=RuntimeError("synthetic input guardrail failure"),
    )

    provider = GuardedSecondReviewProvider(
        reviewer=reviewer,
        guardrail=guardrail,
    )

    workflow, _, repository = _workflow(provider)

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert events == ["guardrail_input"]

    assert reviewer.calls == 0

    assert outcome["status"] == "guardrail_failed"

    assert outcome["guardrail_stage"] == "input"

    assert outcome["effective_route"] == "human_review"

    assert outcome["reason_codes"] == ["guardrail_failure"]

    assert outcome["error_type"] == "RuntimeError"

    assert repository.saved == 2


@pytest.mark.asyncio
async def test_output_guardrail_failure_fails_closed_after_review() -> None:
    events: list[str] = []

    reviewer = FakeReviewer(
        events=events,
        result=_review_result(),
    )

    guardrail = FakeGuardrail(
        events=events,
        output_error=RuntimeError("synthetic output guardrail failure"),
    )

    provider = GuardedSecondReviewProvider(
        reviewer=reviewer,
        guardrail=guardrail,
    )

    workflow, _, repository = _workflow(provider)

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert events == [
        "guardrail_input",
        "review",
        "guardrail_output",
    ]

    assert reviewer.calls == 1

    assert outcome["status"] == "guardrail_failed"

    assert outcome["guardrail_stage"] == "output"

    assert outcome["effective_route"] == "human_review"

    assert outcome["reason_codes"] == ["guardrail_failure"]

    assert outcome["error_type"] == "RuntimeError"

    assert repository.saved == 2


@pytest.mark.asyncio
async def test_allowed_guardrails_reach_decision_gate() -> None:
    events: list[str] = []

    reviewer = FakeReviewer(
        events=events,
        result=_review_result(
            agreement="agree",
            risk_level="medium",
            route="continue",
        ),
    )

    guardrail = FakeGuardrail(
        events=events,
    )

    provider = GuardedSecondReviewProvider(
        reviewer=reviewer,
        guardrail=guardrail,
    )

    workflow, _, repository = _workflow(provider)

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert events == [
        "guardrail_input",
        "review",
        "guardrail_output",
    ]

    assert outcome["status"] == "completed"

    assert outcome["effective_route"] == "continue"

    assert outcome["forced_human_review"] is False

    assert repository.saved == 2


def test_disabled_guardrails_preserve_plain_reviewer() -> None:
    sys.modules.pop(
        "boto3",
        None,
    )

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model",
        aws_bedrock_guardrails_enabled=False,
    )

    provider = build_second_review_provider(settings=settings)

    assert isinstance(
        provider,
        MockBedrockSecondReviewProvider,
    )

    assert not isinstance(
        provider,
        GuardedSecondReviewProvider,
    )

    assert "boto3" not in sys.modules


@pytest.mark.asyncio
async def test_enabled_guardrails_wrap_mock_reviewer_zero_network() -> None:
    sys.modules.pop(
        "boto3",
        None,
    )

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model",
        aws_bedrock_guardrails_enabled=True,
        aws_bedrock_guardrail_id="synthetic-guardrail",
        aws_bedrock_guardrail_version="1",
    )

    provider = build_second_review_provider(settings=settings)

    assert isinstance(
        provider,
        GuardedSecondReviewProvider,
    )

    health = await provider.health()

    assert health["provider"] == "aws-bedrock-mock"

    guardrail_health = health["guardrail"]

    assert isinstance(
        guardrail_health,
        dict,
    )

    assert guardrail_health["provider"] == "aws-bedrock-guardrails-mock"

    assert guardrail_health["network_checked"] is False

    assert "boto3" not in sys.modules
