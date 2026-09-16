from dataclasses import FrozenInstanceError

import pytest

from casemesh.intelligence.contracts import (
    ReviewAgreement,
    ReviewRiskLevel,
    ReviewRoute,
    SecondReviewResult,
)
from casemesh.intelligence.second_review_gate import (
    SecondReviewGateDecision,
    evaluate_second_review,
)


def _review(
    *,
    agreement: ReviewAgreement = "agree",
    risk_level: ReviewRiskLevel = "low",
    recommended_route: ReviewRoute = "continue",
) -> SecondReviewResult:
    return SecondReviewResult(
        provider="synthetic-reviewer",
        model="synthetic-model",
        agreement=agreement,
        risk_level=risk_level,
        concerns=(),
        recommended_route=recommended_route,
        rationale="Synthetic second-review rationale.",
    )


def test_agree_low_continue_can_proceed_to_policy() -> None:
    decision = evaluate_second_review(_review())

    assert decision == SecondReviewGateDecision(
        effective_route="continue",
        provider_route="continue",
        forced_human_review=False,
        reason_codes=(),
    )

    assert decision.can_continue_to_policy is True


def test_agree_medium_continue_can_proceed_to_policy() -> None:
    decision = evaluate_second_review(_review(risk_level="medium"))

    assert decision.effective_route == "continue"
    assert decision.forced_human_review is False
    assert decision.reason_codes == ()
    assert decision.can_continue_to_policy is True


def test_provider_human_review_is_preserved() -> None:
    decision = evaluate_second_review(_review(recommended_route="human_review"))

    assert decision.effective_route == "human_review"
    assert decision.provider_route == "human_review"
    assert decision.forced_human_review is False
    assert decision.reason_codes == ("provider_requested_human_review",)
    assert decision.can_continue_to_policy is False


def test_disagreement_forces_human_review() -> None:
    decision = evaluate_second_review(
        _review(
            agreement="disagree",
            recommended_route="continue",
        )
    )

    assert decision.effective_route == "human_review"
    assert decision.provider_route == "continue"
    assert decision.forced_human_review is True
    assert decision.reason_codes == ("review_disagreed",)


def test_uncertainty_forces_human_review() -> None:
    decision = evaluate_second_review(
        _review(
            agreement="uncertain",
            recommended_route="continue",
        )
    )

    assert decision.effective_route == "human_review"
    assert decision.forced_human_review is True
    assert decision.reason_codes == ("review_uncertain",)


def test_high_risk_forces_human_review() -> None:
    decision = evaluate_second_review(
        _review(
            risk_level="high",
            recommended_route="continue",
        )
    )

    assert decision.effective_route == "human_review"
    assert decision.forced_human_review is True
    assert decision.reason_codes == ("high_risk_review",)


def test_critical_risk_forces_human_review() -> None:
    decision = evaluate_second_review(
        _review(
            risk_level="critical",
            recommended_route="continue",
        )
    )

    assert decision.effective_route == "human_review"
    assert decision.forced_human_review is True
    assert decision.reason_codes == ("critical_risk_review",)


def test_multiple_hard_signals_are_deterministic() -> None:
    decision = evaluate_second_review(
        _review(
            agreement="disagree",
            risk_level="critical",
            recommended_route="continue",
        )
    )

    assert decision.effective_route == "human_review"
    assert decision.reason_codes == (
        "review_disagreed",
        "critical_risk_review",
    )


def test_provider_human_route_and_hard_signal_are_both_recorded() -> None:
    decision = evaluate_second_review(
        _review(
            agreement="uncertain",
            risk_level="high",
            recommended_route="human_review",
        )
    )

    assert decision.effective_route == "human_review"
    assert decision.forced_human_review is False

    assert decision.reason_codes == (
        "provider_requested_human_review",
        "review_uncertain",
        "high_risk_review",
    )


def test_gate_never_exposes_action_execution_permission() -> None:
    decision = evaluate_second_review(_review())

    fields = set(decision.__dataclass_fields__)

    assert "execute" not in fields
    assert "execute_action" not in fields
    assert "action" not in fields
    assert "authorized" not in fields


def test_decision_is_immutable() -> None:
    decision = evaluate_second_review(_review())

    with pytest.raises(FrozenInstanceError):
        decision.effective_route = "human_review"  # type: ignore[misc]
