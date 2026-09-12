from datetime import UTC, datetime

import pytest

from casemesh.evaluation.contracts import (
    BusinessResolution,
    EvaluationCase,
    EvaluationGroundTruth,
)
from casemesh.evaluation.dataset import BenchmarkDataset
from casemesh.evaluation.runner import run_benchmark


def _case(
    evaluation_id: str,
    *,
    scenario_type: str,
    expected_decision: str,
    expected_credit_pct: float | None,
    requires_human_review: bool,
) -> EvaluationCase:
    truth = EvaluationGroundTruth.model_validate(
        {
            "expected_decision": expected_decision,
            "expected_credit_pct": expected_credit_pct,
            "actual_monthly_uptime_pct": 99.8,
            "expected_sla_target_pct": 99.9,
            "contract_eligible_credit_pct": 10.0,
            "requires_human_review": requires_human_review,
            "security_flags": [],
            "forbidden_actions_before_approval": [],
        }
    )

    return EvaluationCase(
        evaluation_id=evaluation_id,
        scenario_type=scenario_type,
        customer_id="CUS-001",
        contract_id="CON-001",
        claim_month="2026-07",
        submitted_at=datetime(2026, 8, 18, 9, tzinfo=UTC),
        requested_credit_pct=10.0,
        case_prompt="Investigate the SLA claim.",
        evidence_files=["contracts/example.pdf"],
        ground_truth=truth,
    )


def _dataset() -> BenchmarkDataset:
    approved = _case(
        "EVAL-0001",
        scenario_type="valid_correct_request",
        expected_decision="approve",
        expected_credit_pct=10.0,
        requires_human_review=False,
    )

    review = _case(
        "EVAL-0002",
        scenario_type="conflicting_evidence",
        expected_decision="human_review",
        expected_credit_pct=None,
        requires_human_review=True,
    )

    return BenchmarkDataset(
        source_directory="test",
        total_records=2,
        unique_records=2,
        duplicate_records=0,
        records=[approved, review],
        unique_cases=[approved, review],
        duplicate_groups=[],
    )


def _approve_resolution() -> BusinessResolution:
    return BusinessResolution(
        decision="approve",
        recommended_credit_pct=10.0,
        requires_human_review=False,
        confidence="high",
        abstained=False,
        reason_codes=[],
    )


def _review_resolution() -> BusinessResolution:
    return BusinessResolution(
        decision="human_review",
        recommended_credit_pct=None,
        requires_human_review=True,
        confidence="medium",
        abstained=False,
        reason_codes=["CONFLICTING_EVIDENCE"],
    )


def test_runner_scores_all_unique_cases() -> None:
    result = run_benchmark(
        dataset=_dataset(),
        resolutions={
            "EVAL-0001": _approve_resolution(),
            "EVAL-0002": _review_resolution(),
        },
    )

    assert result.evaluated_cases == 2
    assert result.metrics.decision_accuracy == 1.0
    assert result.metrics.credit_accuracy == 1.0
    assert result.metrics.human_review_accuracy == 1.0
    assert len(result.cases) == 2


def test_runner_preserves_dataset_counts() -> None:
    result = run_benchmark(
        dataset=_dataset(),
        resolutions={
            "EVAL-0001": _approve_resolution(),
            "EVAL-0002": _review_resolution(),
        },
    )

    assert result.total_dataset_records == 2
    assert result.unique_dataset_records == 2
    assert result.duplicate_dataset_records == 0
    assert result.duplicate_groups == 0


def test_runner_detects_wrong_business_decision() -> None:
    wrong = BusinessResolution(
        decision="deny",
        recommended_credit_pct=0.0,
        requires_human_review=False,
        confidence="high",
        abstained=False,
        reason_codes=[],
    )

    result = run_benchmark(
        dataset=_dataset(),
        resolutions={
            "EVAL-0001": wrong,
            "EVAL-0002": _review_resolution(),
        },
    )

    assert result.metrics.decision_accuracy == 0.5
    assert result.metrics.credit_accuracy == 0.0
    assert result.metrics.human_review_accuracy == 1.0


def test_runner_rejects_missing_resolution() -> None:
    with pytest.raises(ValueError, match="missing=EVAL-0002"):
        run_benchmark(
            dataset=_dataset(),
            resolutions={
                "EVAL-0001": _approve_resolution(),
            },
        )


def test_runner_rejects_unexpected_resolution() -> None:
    with pytest.raises(ValueError, match="unexpected=EVAL-9999"):
        run_benchmark(
            dataset=_dataset(),
            resolutions={
                "EVAL-0001": _approve_resolution(),
                "EVAL-0002": _review_resolution(),
                "EVAL-9999": _approve_resolution(),
            },
        )
