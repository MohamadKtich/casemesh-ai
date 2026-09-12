from casemesh.evaluation.contracts import (
    BusinessResolution,
    EvaluationGroundTruth,
)
from casemesh.evaluation.metrics import (
    score_case,
    summarize_scores,
)


def _truth(
    *,
    decision: str = "approve",
    credit: float | None = 10.0,
    human_review: bool = False,
) -> EvaluationGroundTruth:
    return EvaluationGroundTruth.model_validate(
        {
            "expected_decision": decision,
            "expected_credit_pct": credit,
            "actual_monthly_uptime_pct": 99.8,
            "expected_sla_target_pct": 99.9,
            "contract_eligible_credit_pct": 10.0,
            "requires_human_review": human_review,
            "security_flags": [],
            "forbidden_actions_before_approval": [],
        }
    )


def _resolution(
    *,
    decision: str = "approve",
    credit: float | None = 10.0,
    human_review: bool = False,
    confidence: str = "high",
    abstained: bool = False,
) -> BusinessResolution:
    return BusinessResolution.model_validate(
        {
            "decision": decision,
            "recommended_credit_pct": credit,
            "requires_human_review": human_review,
            "confidence": confidence,
            "abstained": abstained,
            "reason_codes": [],
        }
    )


def test_score_case_accepts_exact_resolution() -> None:
    score = score_case(
        ground_truth=_truth(),
        resolution=_resolution(),
    )

    assert score.decision_correct is True
    assert score.credit_correct is True
    assert score.human_review_correct is True


def test_score_case_detects_wrong_credit() -> None:
    score = score_case(
        ground_truth=_truth(),
        resolution=_resolution(credit=5.0),
    )

    assert score.decision_correct is True
    assert score.credit_correct is False


def test_unresolved_case_excludes_credit_metric() -> None:
    score = score_case(
        ground_truth=_truth(
            decision="human_review",
            credit=None,
            human_review=True,
        ),
        resolution=_resolution(
            decision="human_review",
            credit=None,
            human_review=True,
            confidence="medium",
        ),
    )

    assert score.credit_correct is None


def test_score_case_detects_human_review_mismatch() -> None:
    score = score_case(
        ground_truth=_truth(),
        resolution=_resolution(
            decision="approve",
            credit=10.0,
            human_review=True,
        ),
    )

    assert score.human_review_correct is False


def test_summarize_scores_uses_resolved_credit_denominator() -> None:
    resolved = score_case(
        ground_truth=_truth(),
        resolution=_resolution(),
    )

    unresolved = score_case(
        ground_truth=_truth(
            decision="human_review",
            credit=None,
            human_review=True,
        ),
        resolution=_resolution(
            decision="human_review",
            credit=None,
            human_review=True,
            confidence="medium",
        ),
    )

    summary = summarize_scores([resolved, unresolved])

    assert summary.evaluated_cases == 2
    assert summary.resolved_credit_cases == 1
    assert summary.decision_accuracy == 1.0
    assert summary.credit_accuracy == 1.0
    assert summary.human_review_accuracy == 1.0


def test_summarize_scores_handles_empty_input() -> None:
    summary = summarize_scores([])

    assert summary.evaluated_cases == 0
    assert summary.resolved_credit_cases == 0
    assert summary.decision_accuracy == 0.0
    assert summary.credit_accuracy == 0.0
    assert summary.human_review_accuracy == 0.0
