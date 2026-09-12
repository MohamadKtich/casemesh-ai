import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from casemesh.evaluation.artifacts import (
    EvaluationRunProvenance,
    write_evaluation_artifacts,
)
from casemesh.evaluation.metrics import (
    EvaluationCaseScore,
    EvaluationMetricSummary,
)
from casemesh.evaluation.runner import (
    BenchmarkCaseResult,
    BenchmarkRunResult,
)


def _result() -> BenchmarkRunResult:
    case = BenchmarkCaseResult(
        evaluation_id="EVAL-0001",
        scenario_type="valid_correct_request",
        fingerprint="a" * 64,
        expected_decision="approve",
        actual_decision="approve",
        expected_credit_pct=10.0,
        actual_credit_pct=10.0,
        expected_human_review=False,
        actual_human_review=False,
        score=EvaluationCaseScore(
            decision_correct=True,
            credit_correct=True,
            human_review_correct=True,
        ),
    )

    return BenchmarkRunResult(
        total_dataset_records=100,
        unique_dataset_records=10,
        duplicate_dataset_records=90,
        duplicate_groups=10,
        evaluated_cases=1,
        metrics=EvaluationMetricSummary(
            evaluated_cases=1,
            resolved_credit_cases=1,
            decision_accuracy=1.0,
            credit_accuracy=1.0,
            human_review_accuracy=1.0,
        ),
        cases=[case],
    )


def _provenance() -> EvaluationRunProvenance:
    return EvaluationRunProvenance(
        dataset_name="casemesh-ai-dataset",
        dataset_version="1.0",
        dataset_fingerprint="b" * 64,
        benchmark_profile="sla-deterministic",
        resolution_engine="casemesh.services.sla_resolution.resolve_sla_claim",
        provider="deterministic",
        model=None,
        evaluator_version="0.7.0",
        git_sha="c" * 40,
        source_tree_dirty=False,
    )


def test_provenance_is_written_to_summary(
    tmp_path: Path,
) -> None:
    write_evaluation_artifacts(
        result=_result(),
        output_directory=tmp_path,
        run_id="RUN-PROVENANCE",
        created_at=datetime(2026, 9, 12, 4, tzinfo=UTC),
        provenance=_provenance(),
    )

    payload = json.loads(
        (tmp_path / "evaluation_summary.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["provenance"]["dataset_version"] == "1.0"
    assert payload["provenance"]["provider"] == "deterministic"
    assert payload["provenance"]["model"] is None
    assert payload["provenance"]["source_tree_dirty"] is False


def test_provenance_is_written_to_run_history(
    tmp_path: Path,
) -> None:
    write_evaluation_artifacts(
        result=_result(),
        output_directory=tmp_path,
        run_id="RUN-PROVENANCE",
        created_at=datetime(2026, 9, 12, 4, tzinfo=UTC),
        provenance=_provenance(),
    )

    with (tmp_path / "evaluation_runs.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        row = next(csv.DictReader(handle))

    assert row["dataset_name"] == "casemesh-ai-dataset"
    assert row["dataset_fingerprint"] == "b" * 64
    assert row["benchmark_profile"] == "sla-deterministic"
    assert row["provider"] == "deterministic"
    assert row["git_sha"] == "c" * 40
    assert row["source_tree_dirty"] == "False"


def test_provenance_rejects_invalid_git_sha() -> None:
    with pytest.raises(ValidationError):
        EvaluationRunProvenance(
            dataset_name="casemesh-ai-dataset",
            dataset_version="1.0",
            dataset_fingerprint="b" * 64,
            benchmark_profile="sla-deterministic",
            resolution_engine="resolver",
            provider="deterministic",
            model=None,
            evaluator_version="0.7.0",
            git_sha="not-a-git-sha",
            source_tree_dirty=False,
        )
