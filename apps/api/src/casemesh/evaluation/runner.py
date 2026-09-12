"""Strict deterministic benchmark runner for CaseMesh evaluation."""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from casemesh.evaluation.contracts import (
    BusinessDecision,
    BusinessResolution,
)
from casemesh.evaluation.dataset import (
    BenchmarkDataset,
    case_fingerprint,
)
from casemesh.evaluation.metrics import (
    EvaluationCaseScore,
    EvaluationMetricSummary,
    score_case,
    summarize_scores,
)


class BenchmarkCaseResult(BaseModel):
    """Scored result for one unique benchmark case."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    scenario_type: str
    fingerprint: str = Field(min_length=64, max_length=64)
    expected_decision: BusinessDecision
    actual_decision: BusinessDecision
    expected_credit_pct: float | None
    actual_credit_pct: float | None
    expected_human_review: bool
    actual_human_review: bool
    score: EvaluationCaseScore


class BenchmarkRunResult(BaseModel):
    """Complete deterministic result for one benchmark run."""

    model_config = ConfigDict(extra="forbid")

    total_dataset_records: int = Field(ge=0)
    unique_dataset_records: int = Field(ge=0)
    duplicate_dataset_records: int = Field(ge=0)
    duplicate_groups: int = Field(ge=0)
    evaluated_cases: int = Field(ge=0)
    metrics: EvaluationMetricSummary
    cases: list[BenchmarkCaseResult]


def run_benchmark(
    *,
    dataset: BenchmarkDataset,
    resolutions: Mapping[str, BusinessResolution],
) -> BenchmarkRunResult:
    """Score exactly one resolution for every unique benchmark case."""

    expected_ids = {
        case.evaluation_id
        for case in dataset.unique_cases
    }
    actual_ids = set(resolutions)

    missing_ids = sorted(expected_ids - actual_ids)
    unexpected_ids = sorted(actual_ids - expected_ids)

    if missing_ids or unexpected_ids:
        parts: list[str] = []

        if missing_ids:
            parts.append(
                "missing=" + ",".join(missing_ids)
            )

        if unexpected_ids:
            parts.append(
                "unexpected=" + ",".join(unexpected_ids)
            )

        raise ValueError(
            "Resolution set does not match unique benchmark cases: "
            + "; ".join(parts)
        )

    case_results: list[BenchmarkCaseResult] = []
    scores: list[EvaluationCaseScore] = []

    for case in dataset.unique_cases:
        resolution = resolutions[case.evaluation_id]

        score = score_case(
            ground_truth=case.ground_truth,
            resolution=resolution,
        )

        scores.append(score)

        case_results.append(
            BenchmarkCaseResult(
                evaluation_id=case.evaluation_id,
                scenario_type=case.scenario_type,
                fingerprint=case_fingerprint(case),
                expected_decision=case.ground_truth.expected_decision,
                actual_decision=resolution.decision,
                expected_credit_pct=case.ground_truth.expected_credit_pct,
                actual_credit_pct=resolution.recommended_credit_pct,
                expected_human_review=(
                    case.ground_truth.requires_human_review
                ),
                actual_human_review=(
                    resolution.requires_human_review
                ),
                score=score,
            )
        )

    return BenchmarkRunResult(
        total_dataset_records=dataset.total_records,
        unique_dataset_records=dataset.unique_records,
        duplicate_dataset_records=dataset.duplicate_records,
        duplicate_groups=len(dataset.duplicate_groups),
        evaluated_cases=len(case_results),
        metrics=summarize_scores(scores),
        cases=case_results,
    )
