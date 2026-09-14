import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

from casemesh.api.routes.investigations import (
    build_second_review_provider,
)
from casemesh.core.config import Settings
from casemesh.intelligence.contracts import (
    SecondReviewRequest,
    SecondReviewResult,
)
from casemesh.workflows.investigation import (
    InvestigationWorkflow,
    choose_post_findings_step,
)
from casemesh.workflows.state import InvestigationState

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")
RUN_ID = UUID("22222222-2222-2222-2222-222222222222")
CHUNK_ID = UUID("33333333-3333-3333-3333-333333333333")
DOCUMENT_ID = UUID("44444444-4444-4444-4444-444444444444")


class FakeInvestigationRepository:
    def __init__(self) -> None:
        self.saved = 0

    async def save(
        self,
        run: object,
    ) -> object:
        self.saved += 1
        return run


class FakeSecondReviewProvider:
    provider_name = "synthetic-reviewer"
    model_name = "synthetic-model"

    def __init__(
        self,
        *,
        result: SecondReviewResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0
        self.last_request: SecondReviewRequest | None = None

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        self.calls += 1
        self.last_request = request

        if self.error is not None:
            raise self.error

        if self.result is None:
            raise AssertionError("Synthetic provider result was not configured.")

        return self.result

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


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
        rationale="Synthetic independent review.",
    )


def _state(
    *,
    requested: bool = True,
) -> InvestigationState:
    return {
        "workflow_id": RUN_ID,
        "case_id": CASE_ID,
        "objective": "Determine the supported investigation conclusion.",
        "findings": "Primary evidence-supported finding [E1].",
        "findings_confidence": "medium",
        "findings_abstained": False,
        "citations": [
            {
                "label": "E1",
                "chunk_id": str(CHUNK_ID),
                "document_id": str(DOCUMENT_ID),
                "chunk_index": 2,
                "excerpt": "Synthetic cited evidence.",
            }
        ],
        "gaps": [
            {
                "code": "LOW_CONFIDENCE",
                "description": "Synthetic gap.",
            },
            {
                "code": "LOW_CONFIDENCE",
                "description": "Duplicate synthetic gap.",
            },
            {
                "code": "OTHER_GAP",
                "description": "Another synthetic gap.",
            },
        ],
        "second_review_requested": requested,
    }


def _workflow(
    provider: FakeSecondReviewProvider | None,
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
        settings=Settings(aws_bedrock_review_enabled=False),
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


def test_post_findings_defaults_to_finalize() -> None:
    state: InvestigationState = {}

    assert choose_post_findings_step(state) == "finalize"


def test_explicit_false_routes_to_finalize() -> None:
    state: InvestigationState = {"second_review_requested": False}

    assert choose_post_findings_step(state) == "finalize"


def test_explicit_request_routes_to_second_review() -> None:
    state: InvestigationState = {"second_review_requested": True}

    assert choose_post_findings_step(state) == "second_review"


@pytest.mark.asyncio
async def test_review_request_uses_citations_and_gap_codes() -> None:
    provider = FakeSecondReviewProvider(
        result=_review_result(
            agreement="disagree",
            risk_level="low",
            route="continue",
        )
    )

    workflow, run, repository = _workflow(provider)

    update = await workflow._second_review(_state())

    assert provider.calls == 1
    assert provider.last_request is not None

    request = provider.last_request

    assert request.case_id == CASE_ID
    assert request.investigation_run_id == RUN_ID

    assert request.objective == ("Determine the supported investigation conclusion.")

    assert request.primary_finding == ("Primary evidence-supported finding [E1].")

    assert request.primary_confidence == "medium"
    assert request.primary_abstained is False

    assert len(request.evidence) == 1

    evidence = request.evidence[0]

    assert evidence.chunk_id == CHUNK_ID
    assert evidence.document_id == DOCUMENT_ID
    assert evidence.chunk_index == 2
    assert evidence.citation_label == "E1"
    assert evidence.excerpt == "Synthetic cited evidence."

    assert request.gap_codes == (
        "LOW_CONFIDENCE",
        "OTHER_GAP",
    )

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert outcome["status"] == "completed"
    assert outcome["agreement"] == "disagree"
    assert outcome["provider_route"] == "continue"
    assert outcome["effective_route"] == "human_review"
    assert outcome["forced_human_review"] is True
    assert outcome["reason_codes"] == ["review_disagreed"]

    assert repository.saved == 1
    assert run.current_step == "second_review"

    assert run.metadata_json["existing_metadata"] == "preserved"

    assert run.metadata_json["second_review"]["effective_route"] == "human_review"


@pytest.mark.asyncio
async def test_safe_review_may_continue_to_policy() -> None:
    provider = FakeSecondReviewProvider(
        result=_review_result(
            agreement="agree",
            risk_level="medium",
            route="continue",
        )
    )

    workflow, run, repository = _workflow(provider)

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert outcome["status"] == "completed"
    assert outcome["effective_route"] == "continue"
    assert outcome["forced_human_review"] is False
    assert outcome["reason_codes"] == []

    assert repository.saved == 1
    assert run.metadata_json["second_review"]["effective_route"] == "continue"


@pytest.mark.asyncio
async def test_provider_unavailable_fails_closed_without_exception() -> None:
    workflow, run, repository = _workflow(None)

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert outcome == {
        "status": "unavailable",
        "effective_route": "human_review",
        "forced_human_review": True,
        "reason_codes": ["provider_unavailable"],
    }

    assert repository.saved == 1

    assert run.metadata_json["second_review"]["effective_route"] == "human_review"


@pytest.mark.asyncio
async def test_provider_failure_fails_closed_without_breaking_investigation() -> None:
    provider = FakeSecondReviewProvider(error=RuntimeError("synthetic provider failure"))

    workflow, run, repository = _workflow(provider)

    update = await workflow._second_review(_state())

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert provider.calls == 1

    assert outcome["status"] == "failed"
    assert outcome["effective_route"] == "human_review"
    assert outcome["forced_human_review"] is True
    assert outcome["reason_codes"] == ["provider_failure"]
    assert outcome["error_type"] == "RuntimeError"

    assert repository.saved == 1
    assert run.current_step == "second_review"


@pytest.mark.asyncio
async def test_invalid_review_evidence_fails_closed_before_provider_call() -> None:
    provider = FakeSecondReviewProvider(result=_review_result())

    workflow, _, repository = _workflow(provider)

    state = _state()

    citations = state["citations"]

    citations[0]["chunk_id"] = "not-a-uuid"

    update = await workflow._second_review(state)

    outcome = update["second_review"]

    assert isinstance(
        outcome,
        dict,
    )

    assert provider.calls == 0
    assert outcome["status"] == "failed"
    assert outcome["effective_route"] == "human_review"
    assert outcome["reason_codes"] == ["provider_failure"]
    assert outcome["error_type"] == "ValueError"

    assert repository.saved == 1


def test_disabled_route_builder_returns_no_provider() -> None:
    settings = Settings(
        aws_bedrock_review_enabled=False,
        aws_client_mode="mock",
    )

    provider = build_second_review_provider(settings=settings)

    assert provider is None


def test_mock_route_builder_is_zero_network() -> None:
    sys.modules.pop(
        "boto3",
        None,
    )

    settings = Settings(
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model",
    )

    provider = build_second_review_provider(settings=settings)

    assert provider is not None
    assert provider.provider_name == "aws-bedrock-mock"
    assert provider.model_name == "synthetic-model"

    assert "boto3" not in sys.modules
