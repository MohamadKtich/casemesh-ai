from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from casemesh.intelligence import (
    GuardrailAssessment,
    ReviewEvidence,
    SecondReviewRequest,
    SecondReviewResult,
)


def _review_request() -> SecondReviewRequest:
    return SecondReviewRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        objective="Validate a synthetic finding.",
        primary_finding="Synthetic primary finding.",
        primary_confidence="medium",
        primary_abstained=False,
        evidence=(
            ReviewEvidence(
                chunk_id=UUID("33333333-3333-3333-3333-333333333333"),
                document_id=UUID("44444444-4444-4444-4444-444444444444"),
                chunk_index=0,
                excerpt="Synthetic evidence.",
                citation_label="E1",
            ),
        ),
        gap_codes=("LOW_CONFIDENCE",),
    )


def test_second_review_request_preserves_grounding_context() -> None:
    request = _review_request()

    assert request.primary_confidence == "medium"
    assert request.primary_abstained is False
    assert request.gap_codes == ("LOW_CONFIDENCE",)
    assert len(request.evidence) == 1
    assert request.evidence[0].citation_label == "E1"


def test_second_review_result_supports_human_review_route() -> None:
    result = SecondReviewResult(
        provider="test-provider",
        model="test-model",
        agreement="disagree",
        risk_level="high",
        concerns=("Conflicting evidence.",),
        recommended_route="human_review",
        rationale="Independent reviewer disagreed.",
    )

    assert result.agreement == "disagree"
    assert result.recommended_route == "human_review"
    assert result.risk_level == "high"


def test_guardrail_block_property() -> None:
    allowed = GuardrailAssessment(
        provider="test-provider",
        stage="input",
        decision="allow",
        reason_codes=(),
    )

    blocked = GuardrailAssessment(
        provider="test-provider",
        stage="output",
        decision="block",
        reason_codes=("UNSAFE_OUTPUT",),
    )

    assert allowed.blocked is False
    assert blocked.blocked is True


def test_review_contracts_are_immutable() -> None:
    request = _review_request()

    with pytest.raises(FrozenInstanceError):
        request.primary_finding = "Mutated finding."
