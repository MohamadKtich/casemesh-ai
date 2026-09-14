import sys
from uuid import UUID

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws.bedrock_guardrails import (
    MockBedrockSafetyGuardrailProvider,
    build_mock_bedrock_safety_guardrail_provider,
)
from casemesh.intelligence.contracts import (
    SecondReviewRequest,
    SecondReviewResult,
)

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")

RUN_ID = UUID("22222222-2222-2222-2222-222222222222")


def _request() -> SecondReviewRequest:
    return SecondReviewRequest(
        case_id=CASE_ID,
        investigation_run_id=RUN_ID,
        objective="Synthetic objective.",
        primary_finding="Synthetic primary finding.",
        primary_confidence="medium",
        primary_abstained=False,
        evidence=(),
        gap_codes=(),
    )


def _result() -> SecondReviewResult:
    return SecondReviewResult(
        provider="synthetic-reviewer",
        model="synthetic-model",
        agreement="agree",
        risk_level="low",
        concerns=(),
        recommended_route="continue",
        rationale="Synthetic rationale.",
    )


@pytest.mark.asyncio
async def test_default_input_assessment_allows() -> None:
    provider = MockBedrockSafetyGuardrailProvider(
        guardrail_id="synthetic-guardrail",
        guardrail_version="1",
    )

    assessment = await provider.assess_input(_request())

    assert assessment.provider == ("aws-bedrock-guardrails-mock")
    assert assessment.stage == "input"
    assert assessment.decision == "allow"
    assert assessment.blocked is False
    assert assessment.reason_codes == ()
    assert assessment.message is None


@pytest.mark.asyncio
async def test_default_output_assessment_allows() -> None:
    provider = MockBedrockSafetyGuardrailProvider(
        guardrail_id="synthetic-guardrail",
        guardrail_version="1",
    )

    assessment = await provider.assess_output(
        request=_request(),
        result=_result(),
    )

    assert assessment.stage == "output"
    assert assessment.decision == "allow"
    assert assessment.blocked is False


@pytest.mark.asyncio
async def test_input_block_is_deterministic() -> None:
    provider = MockBedrockSafetyGuardrailProvider(
        guardrail_id="synthetic-guardrail",
        guardrail_version="1",
        input_decision="block",
        input_reason_codes=("PROMPT_INJECTION_SIGNAL",),
        input_message="Synthetic input intervention.",
    )

    assessment = await provider.assess_input(_request())

    assert assessment.blocked is True
    assert assessment.reason_codes == ("PROMPT_INJECTION_SIGNAL",)
    assert assessment.message == ("Synthetic input intervention.")


@pytest.mark.asyncio
async def test_output_block_is_deterministic() -> None:
    provider = MockBedrockSafetyGuardrailProvider(
        guardrail_id="synthetic-guardrail",
        guardrail_version="1",
        output_decision="block",
        output_reason_codes=("GUARDRAIL_INTERVENED",),
        output_message="Synthetic output intervention.",
    )

    assessment = await provider.assess_output(
        request=_request(),
        result=_result(),
    )

    assert assessment.blocked is True
    assert assessment.reason_codes == ("GUARDRAIL_INTERVENED",)


@pytest.mark.asyncio
async def test_health_is_configuration_only() -> None:
    provider = MockBedrockSafetyGuardrailProvider(
        guardrail_id="synthetic-guardrail",
        guardrail_version="1",
    )

    health = await provider.health()

    assert health == {
        "provider": "aws-bedrock-guardrails-mock",
        "mode": "mock",
        "guardrail_id": "synthetic-guardrail",
        "guardrail_version": "1",
        "network_checked": False,
    }


def test_constructor_rejects_blank_identifier() -> None:
    with pytest.raises(
        ValueError,
        match="guardrail_id",
    ):
        MockBedrockSafetyGuardrailProvider(
            guardrail_id=" ",
            guardrail_version="1",
        )


def test_constructor_rejects_blank_version() -> None:
    with pytest.raises(
        ValueError,
        match="guardrail_version",
    ):
        MockBedrockSafetyGuardrailProvider(
            guardrail_id="synthetic-guardrail",
            guardrail_version=" ",
        )


def test_constructor_rejects_blank_reason_codes() -> None:
    with pytest.raises(
        ValueError,
        match="reason_codes",
    ):
        MockBedrockSafetyGuardrailProvider(
            guardrail_id="synthetic-guardrail",
            guardrail_version="1",
            input_reason_codes=(" ",),
        )


def test_blank_message_normalizes_to_none() -> None:
    provider = MockBedrockSafetyGuardrailProvider(
        guardrail_id="synthetic-guardrail",
        guardrail_version="1",
        input_message=" ",
    )

    assert provider._input_message is None


def test_builder_rejects_disabled_guardrails() -> None:
    settings = Settings(
        _env_file=None,
    )

    with pytest.raises(
        ValueError,
        match="aws_bedrock_guardrails_enabled",
    ):
        build_mock_bedrock_safety_guardrail_provider(settings=settings)


def test_builder_rejects_sdk_mode() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model",
        aws_bedrock_guardrails_enabled=True,
        aws_bedrock_guardrail_id="synthetic-guardrail",
        aws_bedrock_guardrail_version="1",
    )

    with pytest.raises(
        ValueError,
        match="aws_client_mode=mock",
    ):
        build_mock_bedrock_safety_guardrail_provider(settings=settings)


def test_builder_is_zero_network() -> None:
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

    provider = build_mock_bedrock_safety_guardrail_provider(settings=settings)

    assert provider.provider_name == ("aws-bedrock-guardrails-mock")

    assert "boto3" not in sys.modules
