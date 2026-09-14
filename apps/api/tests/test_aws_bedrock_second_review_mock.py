import sys
from uuid import UUID

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws.bedrock_review import (
    MockBedrockSecondReviewProvider,
    build_mock_bedrock_second_review_provider,
)
from casemesh.intelligence.contracts import (
    ReviewEvidence,
    SecondReviewRequest,
    SecondReviewResult,
)


def _request(
    *,
    primary_abstained: bool = False,
    gap_codes: tuple[str, ...] = (),
) -> SecondReviewRequest:
    return SecondReviewRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        objective=("Determine whether the evidence supports the primary finding."),
        primary_finding=("The evidence supports the proposed finding."),
        primary_confidence="high",
        primary_abstained=primary_abstained,
        evidence=(
            ReviewEvidence(
                chunk_id=UUID("33333333-3333-3333-3333-333333333333"),
                document_id=UUID("44444444-4444-4444-4444-444444444444"),
                chunk_index=0,
                excerpt="Synthetic evidence excerpt.",
                citation_label="Synthetic Document",
            ),
        ),
        gap_codes=gap_codes,
    )


@pytest.mark.asyncio
async def test_default_mock_returns_agree_low_continue() -> None:
    provider = MockBedrockSecondReviewProvider(model_name="synthetic-bedrock-model")

    result = await provider.review(_request())

    assert result == SecondReviewResult(
        provider="aws-bedrock-mock",
        model="synthetic-bedrock-model",
        agreement="agree",
        risk_level="low",
        concerns=(),
        recommended_route="continue",
        rationale=("Deterministic offline second-review result."),
    )


@pytest.mark.asyncio
async def test_mock_can_model_disagreement_and_human_review() -> None:
    provider = MockBedrockSecondReviewProvider(
        model_name="synthetic-bedrock-model",
        agreement="disagree",
        risk_level="high",
        concerns=("Evidence conflict requires independent review.",),
        recommended_route="human_review",
        rationale=("Synthetic disagreement for deterministic testing."),
    )

    result = await provider.review(_request(gap_codes=("CONFLICTING_EVIDENCE",)))

    assert result.agreement == "disagree"
    assert result.risk_level == "high"
    assert result.recommended_route == "human_review"
    assert result.concerns == ("Evidence conflict requires independent review.",)


@pytest.mark.asyncio
async def test_mock_supports_critical_risk_contract() -> None:
    provider = MockBedrockSecondReviewProvider(
        model_name="synthetic-bedrock-model",
        agreement="uncertain",
        risk_level="critical",
        concerns=("Synthetic critical-risk concern.",),
        recommended_route="human_review",
        rationale=("Synthetic critical-risk review."),
    )

    result = await provider.review(_request(primary_abstained=True))

    assert result.agreement == "uncertain"
    assert result.risk_level == "critical"
    assert result.recommended_route == "human_review"


@pytest.mark.asyncio
async def test_mock_result_is_deterministic_across_repeated_calls() -> None:
    provider = MockBedrockSecondReviewProvider(
        model_name="synthetic-bedrock-model",
        agreement="disagree",
        risk_level="medium",
        concerns=("Synthetic deterministic concern.",),
        recommended_route="human_review",
        rationale="Synthetic deterministic rationale.",
    )

    request = _request()

    first = await provider.review(request)

    second = await provider.review(request)

    assert first == second


@pytest.mark.asyncio
async def test_health_is_zero_network() -> None:
    provider = MockBedrockSecondReviewProvider(model_name="synthetic-bedrock-model")

    health = await provider.health()

    assert health == {
        "provider": "aws-bedrock-mock",
        "model": "synthetic-bedrock-model",
        "mode": "mock",
        "network_checked": False,
    }


def test_constructor_strips_model_and_concerns() -> None:
    provider = MockBedrockSecondReviewProvider(
        model_name="  synthetic-model  ",
        concerns=(
            "  concern one  ",
            "concern two",
        ),
    )

    assert provider.model_name == "synthetic-model"


def test_constructor_rejects_blank_model_name() -> None:
    with pytest.raises(
        ValueError,
        match="model_name",
    ):
        MockBedrockSecondReviewProvider(model_name=" ")


def test_constructor_rejects_blank_rationale() -> None:
    with pytest.raises(
        ValueError,
        match="rationale",
    ):
        MockBedrockSecondReviewProvider(
            model_name="synthetic-model",
            rationale=" ",
        )


def test_constructor_rejects_blank_concern() -> None:
    with pytest.raises(
        ValueError,
        match="concerns",
    ):
        MockBedrockSecondReviewProvider(
            model_name="synthetic-model",
            concerns=(
                "valid concern",
                " ",
            ),
        )


def test_builder_requires_enabled_bedrock_review() -> None:
    settings = Settings(
        _env_file=None,
    )

    with pytest.raises(
        ValueError,
        match="aws_bedrock_review_enabled=true",
    ):
        build_mock_bedrock_second_review_provider(settings=settings)


def test_builder_rejects_sdk_mode() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model",
    )

    with pytest.raises(
        ValueError,
        match="aws_client_mode=mock",
    ):
        build_mock_bedrock_second_review_provider(settings=settings)


@pytest.mark.asyncio
async def test_builder_mock_mode_never_loads_boto3() -> None:
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
    )

    provider = build_mock_bedrock_second_review_provider(settings=settings)

    result = await provider.review(_request())

    assert result.provider == "aws-bedrock-mock"
    assert result.model == "synthetic-model"
    assert "boto3" not in sys.modules
