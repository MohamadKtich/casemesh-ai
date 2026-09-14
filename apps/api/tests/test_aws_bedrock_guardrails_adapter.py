import json
import sys
import time
from uuid import UUID

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws.bedrock_guardrails import (
    BedrockGuardrailTimeoutError,
    BedrockSafetyGuardrailProvider,
    build_bedrock_safety_guardrail_provider,
)
from casemesh.integrations.aws.gateway import (
    AWSClientAccessError,
    AWSIntelligenceGateway,
)
from casemesh.intelligence.contracts import (
    SecondReviewRequest,
    SecondReviewResult,
)

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")

RUN_ID = UUID("22222222-2222-2222-2222-222222222222")


class RecordingClient:
    def __init__(
        self,
        response: object,
    ) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def apply_guardrail(
        self,
        **kwargs: object,
    ) -> object:
        self.calls.append(dict(kwargs))

        return self.response


class FailingClient:
    def apply_guardrail(
        self,
        **kwargs: object,
    ) -> object:
        _ = kwargs
        raise RuntimeError("synthetic apply_guardrail failure")


class SlowClient:
    def apply_guardrail(
        self,
        **kwargs: object,
    ) -> object:
        _ = kwargs

        time.sleep(0.03)

        return {
            "action": "NONE",
            "outputs": [],
        }


class RecordingFactory:
    def __init__(
        self,
        client: object,
    ) -> None:
        self.client = client
        self.calls: list[tuple[str, str]] = []

    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        self.calls.append(
            (
                service_name,
                region_name,
            )
        )

        return self.client


def _request() -> SecondReviewRequest:
    return SecondReviewRequest(
        case_id=CASE_ID,
        investigation_run_id=RUN_ID,
        objective="Synthetic objective.",
        primary_finding="Synthetic finding.",
        primary_confidence="medium",
        primary_abstained=False,
        evidence=(),
        gap_codes=("LOW_CONFIDENCE",),
    )


def _result() -> SecondReviewResult:
    return SecondReviewResult(
        provider="synthetic-reviewer",
        model="synthetic-model",
        agreement="agree",
        risk_level="low",
        concerns=("Synthetic concern.",),
        recommended_route="continue",
        rationale="Synthetic rationale.",
    )


@pytest.mark.asyncio
async def test_input_uses_apply_guardrail_shape() -> None:
    client = RecordingClient(
        {
            "action": "NONE",
            "outputs": [],
            "assessments": [],
        }
    )

    provider = BedrockSafetyGuardrailProvider(
        client=client,
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    assessment = await provider.assess_input(_request())

    assert assessment.stage == "input"
    assert assessment.decision == "allow"
    assert assessment.blocked is False

    assert len(client.calls) == 1

    call = client.calls[0]

    assert call["guardrailIdentifier"] == "guardrail-123"

    assert call["guardrailVersion"] == "1"

    assert call["source"] == "INPUT"
    assert call["outputScope"] == "INTERVENTIONS"

    content = call["content"]

    assert isinstance(
        content,
        list,
    )

    block = content[0]

    assert isinstance(
        block,
        dict,
    )

    text_block = block["text"]

    assert isinstance(
        text_block,
        dict,
    )

    document = json.loads(text_block["text"])

    assert document["case_id"] == str(CASE_ID)

    assert document["investigation_run_id"] == str(RUN_ID)

    assert document["primary_finding"] == "Synthetic finding."

    assert document["gap_codes"] == ["LOW_CONFIDENCE"]


@pytest.mark.asyncio
async def test_output_uses_output_source() -> None:
    client = RecordingClient(
        {
            "action": "NONE",
            "outputs": [],
        }
    )

    provider = BedrockSafetyGuardrailProvider(
        client=client,
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    assessment = await provider.assess_output(
        request=_request(),
        result=_result(),
    )

    assert assessment.stage == "output"
    assert assessment.decision == "allow"

    call = client.calls[0]

    assert call["source"] == "OUTPUT"

    content = call["content"]

    assert isinstance(
        content,
        list,
    )

    block = content[0]

    assert isinstance(
        block,
        dict,
    )

    text_block = block["text"]

    assert isinstance(
        text_block,
        dict,
    )

    document = json.loads(text_block["text"])

    assert document["agreement"] == "agree"

    assert document["recommended_route"] == "continue"

    assert document["rationale"] == "Synthetic rationale."


@pytest.mark.asyncio
async def test_intervention_maps_to_block() -> None:
    client = RecordingClient(
        {
            "action": "GUARDRAIL_INTERVENED",
            "actionReason": ("Synthetic safety intervention."),
            "outputs": [{"text": "Blocked output."}],
        }
    )

    provider = BedrockSafetyGuardrailProvider(
        client=client,
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    assessment = await provider.assess_input(_request())

    assert assessment.decision == "block"
    assert assessment.blocked is True

    assert assessment.reason_codes == ("GUARDRAIL_INTERVENED",)

    assert assessment.message == ("Synthetic safety intervention.")


@pytest.mark.asyncio
async def test_output_text_used_when_action_reason_absent() -> None:
    client = RecordingClient(
        {
            "action": "GUARDRAIL_INTERVENED",
            "outputs": [{"text": "Synthetic blocked content."}],
        }
    )

    provider = BedrockSafetyGuardrailProvider(
        client=client,
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    assessment = await provider.assess_output(
        request=_request(),
        result=_result(),
    )

    assert assessment.message == ("Synthetic blocked content.")


@pytest.mark.asyncio
async def test_unknown_action_is_rejected() -> None:
    provider = BedrockSafetyGuardrailProvider(
        client=RecordingClient(
            {
                "action": "FUTURE_ACTION",
                "outputs": [],
            }
        ),
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    with pytest.raises(
        ValueError,
        match="unsupported action",
    ):
        await provider.assess_input(_request())


@pytest.mark.asyncio
async def test_missing_action_is_rejected() -> None:
    provider = BedrockSafetyGuardrailProvider(
        client=RecordingClient(
            {
                "outputs": [],
            }
        ),
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    with pytest.raises(
        ValueError,
        match="action",
    ):
        await provider.assess_input(_request())


@pytest.mark.asyncio
async def test_non_mapping_response_is_rejected() -> None:
    provider = BedrockSafetyGuardrailProvider(
        client=RecordingClient([]),
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    with pytest.raises(
        ValueError,
        match="mapping",
    ):
        await provider.assess_input(_request())


@pytest.mark.asyncio
async def test_invalid_outputs_shape_is_rejected() -> None:
    provider = BedrockSafetyGuardrailProvider(
        client=RecordingClient(
            {
                "action": "GUARDRAIL_INTERVENED",
                "outputs": "invalid",
            }
        ),
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    with pytest.raises(
        ValueError,
        match="outputs",
    ):
        await provider.assess_input(_request())


@pytest.mark.asyncio
async def test_client_failure_propagates() -> None:
    provider = BedrockSafetyGuardrailProvider(
        client=FailingClient(),
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic apply_guardrail failure",
    ):
        await provider.assess_input(_request())


@pytest.mark.asyncio
async def test_timeout_is_typed() -> None:
    provider = BedrockSafetyGuardrailProvider(
        client=SlowClient(),
        guardrail_id="guardrail-123",
        guardrail_version="1",
        request_timeout_seconds=0.001,
    )

    with pytest.raises(
        BedrockGuardrailTimeoutError,
    ):
        await provider.assess_input(_request())


@pytest.mark.asyncio
async def test_health_is_zero_network() -> None:
    client = RecordingClient(
        {
            "action": "NONE",
            "outputs": [],
        }
    )

    provider = BedrockSafetyGuardrailProvider(
        client=client,
        guardrail_id="guardrail-123",
        guardrail_version="1",
    )

    health = await provider.health()

    assert health["api"] == "apply_guardrail"

    assert health["network_checked"] is False

    assert client.calls == []


def test_gateway_rejects_disabled_guardrails() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
    )

    gateway = AWSIntelligenceGateway(settings)

    with pytest.raises(
        AWSClientAccessError,
        match="bedrock_guardrails",
    ):
        gateway.bedrock_guardrails_runtime_client()


def test_sdk_builder_uses_guardrail_gateway_boundary() -> None:
    client = RecordingClient(
        {
            "action": "NONE",
            "outputs": [],
        }
    )

    factory = RecordingFactory(client)

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_bedrock_review_enabled=True,
        aws_bedrock_model_id="synthetic-model",
        aws_bedrock_guardrails_enabled=True,
        aws_bedrock_guardrail_id="guardrail-123",
        aws_bedrock_guardrail_version="1",
    )

    gateway = AWSIntelligenceGateway(
        settings,
        client_factory=factory,
    )

    provider = build_bedrock_safety_guardrail_provider(
        settings=settings,
        gateway=gateway,
    )

    assert provider.provider_name == ("aws-bedrock-guardrails")

    assert factory.calls == [
        (
            "bedrock-runtime",
            "me-central-1",
        )
    ]


def test_mock_builder_remains_zero_network() -> None:
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
        aws_bedrock_guardrail_id="guardrail-123",
        aws_bedrock_guardrail_version="1",
    )

    gateway = AWSIntelligenceGateway(settings)

    provider = build_bedrock_safety_guardrail_provider(
        settings=settings,
        gateway=gateway,
    )

    assert provider.provider_name == ("aws-bedrock-guardrails-mock")

    assert "boto3" not in sys.modules
