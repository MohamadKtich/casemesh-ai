import json
from pathlib import Path

import pytest

import casemesh.evaluation.stability as stability_module
from casemesh.evaluation.dataset import BenchmarkDataset
from casemesh.evaluation.metrics import (
    EvaluationCaseScore,
    EvaluationMetricSummary,
)
from casemesh.evaluation.runner import (
    BenchmarkCaseResult,
    BenchmarkRunResult,
)
from casemesh.evaluation.stability import (
    evaluate_repeatability,
    write_stability_artifact,
)


def _case(
    *,
    actual_decision: str = "approve",
    decision_correct: bool = True,
) -> BenchmarkCaseResult:
    return BenchmarkCaseResult(
        evaluation_id="EVAL-0001",
        scenario_type="valid_correct_request",
        fingerprint="a" * 64,
        expected_decision="approve",
        actual_decision=actual_decision,
        expected_credit_pct=10.0,
        actual_credit_pct=10.0,
        expected_human_review=False,
        actual_human_review=False,
        score=EvaluationCaseScore(
            decision_correct=decision_correct,
            credit_correct=True,
            human_review_correct=True,
        ),
    )


def _result(
    *,
    actual_decision: str = "approve",
    decision_accuracy: float = 1.0,
    decision_correct: bool = True,
) -> BenchmarkRunResult:
    return BenchmarkRunResult(
        total_dataset_records=100,
        unique_dataset_records=10,
        duplicate_dataset_records=90,
        duplicate_groups=10,
        evaluated_cases=1,
        metrics=EvaluationMetricSummary(
            evaluated_cases=1,
            resolved_credit_cases=1,
            decision_accuracy=decision_accuracy,
            credit_accuracy=1.0,
            human_review_accuracy=1.0,
        ),
        cases=[
            _case(
                actual_decision=actual_decision,
                decision_correct=decision_correct,
            )
        ],
    )


def _dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        source_directory="synthetic",
        total_records=100,
        unique_records=10,
        duplicate_records=90,
        records=[],
        unique_cases=[],
        duplicate_groups=[],
    )


def _evaluate(
    *,
    repeated_runs: int,
) -> object:
    return evaluate_repeatability(
        dataset=_dataset(),
        dataset_root=Path("."),
        baseline_result=_result(),
        dataset_fingerprint="b" * 64,
        baseline_run_id="baseline",
        baseline_source_git_sha="c" * 40,
        stability_evaluator_git_sha="d" * 40,
        source_tree_dirty=False,
        repeated_runs=repeated_runs,
    )


def test_repeatability_is_stable_for_identical_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _result()

    def fake_run(**_: object) -> BenchmarkRunResult:
        return baseline

    monkeypatch.setattr(
        stability_module,
        "run_sla_dataset_benchmark",
        fake_run,
    )

    result = _evaluate(repeated_runs=3)

    assert result.stable is True
    assert result.repeated_runs == 3
    assert result.total_case_executions == 30
    assert result.unique_result_hashes == 1
    assert result.decision_stability == 1.0
    assert result.credit_stability == 1.0
    assert result.human_review_stability == 1.0


def test_repeatability_detects_divergent_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = iter([
        _result(),
        _result(
            actual_decision="deny",
            decision_accuracy=0.0,
            decision_correct=False,
        ),
    ])

    def fake_run(**_: object) -> BenchmarkRunResult:
        return next(results)

    monkeypatch.setattr(
        stability_module,
        "run_sla_dataset_benchmark",
        fake_run,
    )

    result = _evaluate(repeated_runs=2)

    assert result.stable is False
    assert result.unique_result_hashes == 2
    assert result.repeated_result_hash is None
    assert result.decision_stability == 0.5


def test_stability_artifact_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _result()

    def fake_run(**_: object) -> BenchmarkRunResult:
        return baseline

    monkeypatch.setattr(
        stability_module,
        "run_sla_dataset_benchmark",
        fake_run,
    )

    result = _evaluate(repeated_runs=2)
    path = tmp_path / "evaluation_stability.json"

    write_stability_artifact(result=result, path=path)

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["stable"] is True
    assert payload["repeated_runs"] == 2
    assert payload["timing_scope"] == "local_diagnostic_only"
    assert payload["source_tree_dirty"] is False


def test_repeatability_rejects_zero_runs() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        _evaluate(repeated_runs=0)
