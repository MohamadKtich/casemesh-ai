"""Deterministic metrics for CaseMesh benchmark evaluation."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from casemesh.evaluation.contracts import (
    BusinessResolution,
    EvaluationGroundTruth,
)

CREDIT_TOLERANCE = 1e-6


class EvaluationCaseScore(BaseModel):
    """Metric outcomes for one benchmark case."""

    model_config = ConfigDict(extra="forbid")

    decision_correct: bool
    credit_correct: bool | None
    human_review_correct: bool


class EvaluationMetricSummary(BaseModel):
    """Aggregate deterministic benchmark metrics."""

    model_config = ConfigDict(extra="forbid")

    evaluated_cases: int = Field(ge=0)
    resolved_credit_cases: int = Field(ge=0)
    decision_accuracy: float = Field(ge=0, le=1)
    credit_accuracy: float = Field(ge=0, le=1)
    human_review_accuracy: float = Field(ge=0, le=1)


def score_case(
    *,
    ground_truth: EvaluationGroundTruth,
    resolution: BusinessResolution,
) -> EvaluationCaseScore:
    """Score one normalized resolution against benchmark ground truth."""

    decision_correct = resolution.decision == ground_truth.expected_decision

    credit_correct: bool | None
    if ground_truth.expected_credit_pct is None:
        credit_correct = None
    elif resolution.recommended_credit_pct is None:
        credit_correct = False
    else:
        credit_correct = (
            abs(
                resolution.recommended_credit_pct
                - ground_truth.expected_credit_pct
            )
            <= CREDIT_TOLERANCE
        )

    human_review_correct = (
        resolution.requires_human_review
        == ground_truth.requires_human_review
    )

    return EvaluationCaseScore(
        decision_correct=decision_correct,
        credit_correct=credit_correct,
        human_review_correct=human_review_correct,
    )


def summarize_scores(
    scores: Sequence[EvaluationCaseScore],
) -> EvaluationMetricSummary:
    """Aggregate per-case deterministic scores."""

    total = len(scores)

    if total == 0:
        return EvaluationMetricSummary(
            evaluated_cases=0,
            resolved_credit_cases=0,
            decision_accuracy=0.0,
            credit_accuracy=0.0,
            human_review_accuracy=0.0,
        )

    decision_hits = sum(score.decision_correct for score in scores)
    human_review_hits = sum(
        score.human_review_correct
        for score in scores
    )

    credit_scores = [
        score.credit_correct
        for score in scores
        if score.credit_correct is not None
    ]

    resolved_credit_cases = len(credit_scores)
    credit_hits = sum(
        credit_score
        for credit_score in credit_scores
        if credit_score is not None
    )

    credit_accuracy = (
        credit_hits / resolved_credit_cases
        if resolved_credit_cases
        else 0.0
    )

    return EvaluationMetricSummary(
        evaluated_cases=total,
        resolved_credit_cases=resolved_credit_cases,
        decision_accuracy=decision_hits / total,
        credit_accuracy=credit_accuracy,
        human_review_accuracy=human_review_hits / total,
    )
