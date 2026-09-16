import json
from uuid import UUID

import pytest

from casemesh.integrations.aws.bedrock_review import (
    BEDROCK_REVIEW_MAX_CONCERN_CHARS,
    BEDROCK_REVIEW_MAX_CONCERNS,
    BEDROCK_REVIEW_MAX_RATIONALE_CHARS,
    BEDROCK_REVIEW_MAX_RESPONSE_CHARS,
    BEDROCK_REVIEW_RESPONSE_SCHEMA,
    BedrockReviewStopReasonError,
    BedrockSecondReviewProvider,
)
from casemesh.intelligence.contracts import (
    SecondReviewRequest,
)

MODEL_ID = "synthetic-bedrock-model"


class Client:
    def __init__(
        self,
        response: object,
    ) -> None:
        self.response = response

    def converse(
        self,
        **kwargs: object,
    ) -> object:
        _ = kwargs
        return self.response


def _request() -> SecondReviewRequest:
    return SecondReviewRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        objective="Synthetic objective.",
        primary_finding="Synthetic primary finding.",
        primary_confidence="medium",
        primary_abstained=False,
        evidence=(),
        gap_codes=(),
    )


def _document(
    *,
    concerns: object | None = None,
    rationale: object = "Synthetic rationale.",
) -> dict[str, object]:
    return {
        "agreement": "agree",
        "risk_level": "low",
        "concerns": ([] if concerns is None else concerns),
        "recommended_route": "continue",
        "rationale": rationale,
    }


def _response(
    *,
    stop_reason: object = "end_turn",
    document: dict[str, object] | None = None,
    raw_text: str | None = None,
) -> dict[str, object]:
    text = json.dumps(document or _document()) if raw_text is None else raw_text

    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": stop_reason,
    }


@pytest.mark.parametrize(
    "stop_reason",
    [
        "tool_use",
        "max_tokens",
        "stop_sequence",
        "guardrail_intervened",
        "content_filtered",
        "malformed_model_output",
        "malformed_tool_use",
        "model_context_window_exceeded",
        "future_unknown_reason",
    ],
)
@pytest.mark.asyncio
async def test_non_end_turn_stop_reason_fails_closed(
    stop_reason: str,
) -> None:
    provider = BedrockSecondReviewProvider(
        client=Client(_response(stop_reason=stop_reason)),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        BedrockReviewStopReasonError,
    ) as exc_info:
        await provider.review(_request())

    assert exc_info.value.stop_reason == stop_reason


@pytest.mark.asyncio
async def test_valid_json_is_not_trusted_after_max_tokens() -> None:
    provider = BedrockSecondReviewProvider(
        client=Client(
            _response(
                stop_reason="max_tokens",
                document=_document(),
            )
        ),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        BedrockReviewStopReasonError,
        match="max_tokens",
    ):
        await provider.review(_request())


@pytest.mark.parametrize(
    "stop_reason",
    [
        None,
        123,
        True,
        {},
        [],
    ],
)
@pytest.mark.asyncio
async def test_non_string_stop_reason_is_rejected(
    stop_reason: object,
) -> None:
    provider = BedrockSecondReviewProvider(
        client=Client(_response(stop_reason=stop_reason)),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        ValueError,
        match="stopReason",
    ):
        await provider.review(_request())


@pytest.mark.asyncio
async def test_blank_stop_reason_is_rejected() -> None:
    provider = BedrockSecondReviewProvider(
        client=Client(_response(stop_reason=" ")),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        ValueError,
        match="stopReason",
    ):
        await provider.review(_request())


@pytest.mark.asyncio
async def test_missing_stop_reason_is_rejected() -> None:
    response = _response()
    del response["stopReason"]

    provider = BedrockSecondReviewProvider(
        client=Client(response),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        ValueError,
        match="stopReason",
    ):
        await provider.review(_request())


@pytest.mark.asyncio
async def test_raw_response_size_is_bounded() -> None:
    provider = BedrockSecondReviewProvider(
        client=Client(_response(raw_text=("x" * (BEDROCK_REVIEW_MAX_RESPONSE_CHARS + 1)))),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        ValueError,
        match="application limit",
    ):
        await provider.review(_request())


@pytest.mark.asyncio
async def test_concern_count_is_bounded() -> None:
    concerns = [f"concern-{index}" for index in range(BEDROCK_REVIEW_MAX_CONCERNS + 1)]

    provider = BedrockSecondReviewProvider(
        client=Client(_response(document=_document(concerns=concerns))),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        ValueError,
        match="concerns.*application limit",
    ):
        await provider.review(_request())


@pytest.mark.asyncio
async def test_individual_concern_size_is_bounded() -> None:
    provider = BedrockSecondReviewProvider(
        client=Client(
            _response(document=_document(concerns=["x" * (BEDROCK_REVIEW_MAX_CONCERN_CHARS + 1)]))
        ),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        ValueError,
        match="concern.*application limit",
    ):
        await provider.review(_request())


@pytest.mark.asyncio
async def test_rationale_size_is_bounded() -> None:
    provider = BedrockSecondReviewProvider(
        client=Client(
            _response(
                document=_document(rationale=("x" * (BEDROCK_REVIEW_MAX_RATIONALE_CHARS + 1)))
            )
        ),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        ValueError,
        match="rationale.*application limit",
    ):
        await provider.review(_request())


@pytest.mark.parametrize(
    "concerns",
    [
        [123],
        [True],
        [{}],
        [[]],
    ],
)
@pytest.mark.asyncio
async def test_concerns_reject_non_string_values(
    concerns: list[object],
) -> None:
    provider = BedrockSecondReviewProvider(
        client=Client(_response(document=_document(concerns=concerns))),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        ValueError,
        match="only strings",
    ):
        await provider.review(_request())


@pytest.mark.parametrize(
    "rationale",
    [
        123,
        True,
        {},
        [],
    ],
)
@pytest.mark.asyncio
async def test_rationale_rejects_non_string_values(
    rationale: object,
) -> None:
    provider = BedrockSecondReviewProvider(
        client=Client(_response(document=_document(rationale=rationale))),
        model_name=MODEL_ID,
    )

    with pytest.raises(
        ValueError,
        match="rationale",
    ):
        await provider.review(_request())


def test_second_review_schema_has_no_action_execution_surface() -> None:
    properties = BEDROCK_REVIEW_RESPONSE_SCHEMA["properties"]

    assert isinstance(
        properties,
        dict,
    )

    assert "action" not in properties
    assert "execute" not in properties
    assert "execute_action" not in properties
    assert "tool" not in properties

    route = properties["recommended_route"]

    assert isinstance(
        route,
        dict,
    )

    assert route["enum"] == [
        "continue",
        "human_review",
    ]

    assert BEDROCK_REVIEW_RESPONSE_SCHEMA["additionalProperties"] is False
