import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from casemesh.evaluation.artifacts import (
    is_failed_case,
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


def _case_result(
    *,
    evaluation_id: str = "EVAL-0001",
    decision_correct: bool = True,
    credit_correct: bool | None = True,
    human_review_correct: bool = True,
) -> BenchmarkCaseResult:
    return BenchmarkCaseResult(
        evaluation_id=evaluation_id,
        scenario_type="valid_correct_request",
        fingerprint="a" * 64,
        expected_decision="approve",
        actual_decision=("approve" if decision_correct else "deny"),
        expected_credit_pct=10.0,
        actual_credit_pct=(10.0 if credit_correct is not False else 0.0),
        expected_human_review=False,
        actual_human_review=not human_review_correct,
        score=EvaluationCaseScore(
            decision_correct=decision_correct,
            credit_correct=credit_correct,
            human_review_correct=human_review_correct,
        ),
    )


def _run_result(
    cases: list[BenchmarkCaseResult],
) -> BenchmarkRunResult:
    total = len(cases)
    decision_hits = sum(case.score.decision_correct for case in cases)
    review_hits = sum(case.score.human_review_correct for case in cases)

    applicable_credit = [
        case.score.credit_correct
        for case in cases
        if case.score.credit_correct is not None
    ]
    credit_hits = sum(value is True for value in applicable_credit)

    return BenchmarkRunResult(
        total_dataset_records=100,
        unique_dataset_records=10,
        duplicate_dataset_records=90,
        duplicate_groups=10,
        evaluated_cases=total,
        metrics=EvaluationMetricSummary(
            evaluated_cases=total,
            resolved_credit_cases=len(applicable_credit),
            decision_accuracy=(decision_hits / total if total else 0.0),
            credit_accuracy=(
                credit_hits / len(applicable_credit)
                if applicable_credit
                else 0.0
            ),
            human_review_accuracy=(
                review_hits / total
                if total
                else 0.0
            ),
        ),
        cases=cases,
    )


def test_is_failed_case_requires_applicable_failure() -> None:
    assert is_failed_case(_case_result()) is False
    assert is_failed_case(_case_result(credit_correct=None)) is False
    assert is_failed_case(
        _case_result(decision_correct=False)
    ) is True
    assert is_failed_case(
        _case_result(credit_correct=False)
    ) is True
    assert is_failed_case(
        _case_result(human_review_correct=False)
    ) is True


def test_writer_creates_all_artifacts(tmp_path: Path) -> None:
    result = _run_result([_case_result()])

    paths = write_evaluation_artifacts(
        result=result,
        output_directory=tmp_path,
        run_id="RUN-001",
        created_at=datetime(2026, 9, 12, 3, tzinfo=UTC),
    )

    assert Path(paths.results_json).exists()
    assert Path(paths.summary_json).exists()
    assert Path(paths.failures_json).exists()
    assert Path(paths.runs_csv).exists()


def test_summary_records_dataset_and_metrics(tmp_path: Path) -> None:
    result = _run_result([_case_result()])

    write_evaluation_artifacts(
        result=result,
        output_directory=tmp_path,
        run_id="RUN-001",
        created_at=datetime(2026, 9, 12, 3, tzinfo=UTC),
    )

    payload = json.loads(
        (tmp_path / "evaluation_summary.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["run_id"] == "RUN-001"
    assert payload["dataset"]["total_records"] == 100
    assert payload["dataset"]["unique_records"] == 10
    assert payload["dataset"]["duplicate_records"] == 90
    assert payload["metrics"]["decision_accuracy"] == 1.0
    assert payload["failed_cases"] == 0


def test_failures_artifact_contains_only_failed_cases(
    tmp_path: Path,
) -> None:
    passed = _case_result(evaluation_id="EVAL-0001")
    failed = _case_result(
        evaluation_id="EVAL-0002",
        decision_correct=False,
    )

    write_evaluation_artifacts(
        result=_run_result([passed, failed]),
        output_directory=tmp_path,
        run_id="RUN-002",
        created_at=datetime(2026, 9, 12, 3, tzinfo=UTC),
    )

    payload = json.loads(
        (tmp_path / "evaluation_failures.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["failed_cases"] == 1
    assert len(payload["cases"]) == 1
    assert payload["cases"][0]["evaluation_id"] == "EVAL-0002"


def test_run_history_appends_without_repeating_header(
    tmp_path: Path,
) -> None:
    result = _run_result([_case_result()])
    timestamp = datetime(2026, 9, 12, 3, tzinfo=UTC)

    write_evaluation_artifacts(
        result=result,
        output_directory=tmp_path,
        run_id="RUN-001",
        created_at=timestamp,
    )
    write_evaluation_artifacts(
        result=result,
        output_directory=tmp_path,
        run_id="RUN-002",
        created_at=timestamp,
    )

    with (tmp_path / "evaluation_runs.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert [row["run_id"] for row in rows] == [
        "RUN-001",
        "RUN-002",
    ]


def test_writer_rejects_empty_run_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="run_id"):
        write_evaluation_artifacts(
            result=_run_result([_case_result()]),
            output_directory=tmp_path,
            run_id="   ",
        )


def test_writer_rejects_naive_timestamp(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        write_evaluation_artifacts(
            result=_run_result([_case_result()]),
            output_directory=tmp_path,
            run_id="RUN-001",
            created_at=datetime(2026, 9, 12, 3),
        )
