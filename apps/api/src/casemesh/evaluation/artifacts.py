"""Persistent JSON and CSV artifacts for CaseMesh evaluation runs."""

import csv
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from casemesh.evaluation.runner import (
    BenchmarkCaseResult,
    BenchmarkRunResult,
)


class EvaluationArtifactPaths(BaseModel):
    """Paths written for one benchmark artifact export."""

    model_config = ConfigDict(extra="forbid")

    results_json: str
    summary_json: str
    failures_json: str
    runs_csv: str


class EvaluationRunProvenance(BaseModel):
    """Reproducibility metadata describing one benchmark execution."""

    model_config = ConfigDict(extra="forbid")

    dataset_name: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    dataset_fingerprint: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    benchmark_profile: str = Field(min_length=1)
    resolution_engine: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str | None = None
    evaluator_version: str = Field(min_length=1)
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree_dirty: bool


def is_failed_case(case: BenchmarkCaseResult) -> bool:
    """Return whether a benchmark case failed any applicable core metric."""

    return (
        not case.score.decision_correct
        or not case.score.human_review_correct
        or case.score.credit_correct is False
    )


def write_evaluation_artifacts(
    *,
    result: BenchmarkRunResult,
    output_directory: Path,
    run_id: str,
    created_at: datetime | None = None,
    provenance: EvaluationRunProvenance | None = None,
) -> EvaluationArtifactPaths:
    """Write benchmark JSON artifacts and append run history."""

    if not run_id.strip():
        raise ValueError("run_id must not be empty.")

    timestamp = created_at or datetime.now(UTC)

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware.")

    output_directory.mkdir(parents=True, exist_ok=True)

    results_path = output_directory / "evaluation_results.json"
    summary_path = output_directory / "evaluation_summary.json"
    failures_path = output_directory / "evaluation_failures.json"
    runs_path = output_directory / "evaluation_runs.csv"

    metadata: dict[str, object] = {
        "run_id": run_id,
        "created_at": timestamp.isoformat(),
    }

    if provenance is not None:
        metadata["provenance"] = provenance.model_dump(mode="json")

    failures = [
        case
        for case in result.cases
        if is_failed_case(case)
    ]

    results_payload = {
        **metadata,
        "benchmark": result.model_dump(mode="json"),
    }

    summary_payload = {
        **metadata,
        "dataset": {
            "total_records": result.total_dataset_records,
            "unique_records": result.unique_dataset_records,
            "duplicate_records": result.duplicate_dataset_records,
            "duplicate_groups": result.duplicate_groups,
        },
        "evaluated_cases": result.evaluated_cases,
        "failed_cases": len(failures),
        "metrics": result.metrics.model_dump(mode="json"),
    }

    failures_payload = {
        **metadata,
        "failed_cases": len(failures),
        "cases": [
            case.model_dump(mode="json")
            for case in failures
        ],
    }

    _write_json(results_path, results_payload)
    _write_json(summary_path, summary_payload)
    _write_json(failures_path, failures_payload)

    _append_run_history(
        path=runs_path,
        run_id=run_id,
        created_at=timestamp,
        result=result,
        failed_cases=len(failures),
        provenance=provenance,
    )

    return EvaluationArtifactPaths(
        results_json=str(results_path),
        summary_json=str(summary_path),
        failures_json=str(failures_path),
        runs_csv=str(runs_path),
    )


def _write_json(
    path: Path,
    payload: Mapping[str, object],
) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _append_run_history(
    *,
    path: Path,
    run_id: str,
    created_at: datetime,
    result: BenchmarkRunResult,
    failed_cases: int,
    provenance: EvaluationRunProvenance | None,
) -> None:
    fieldnames = [
        "run_id",
        "created_at",
        "dataset_name",
        "dataset_version",
        "dataset_fingerprint",
        "benchmark_profile",
        "resolution_engine",
        "provider",
        "model",
        "evaluator_version",
        "git_sha",
        "source_tree_dirty",
        "total_dataset_records",
        "unique_dataset_records",
        "duplicate_dataset_records",
        "evaluated_cases",
        "failed_cases",
        "decision_accuracy",
        "credit_accuracy",
        "human_review_accuracy",
    ]

    row: dict[str, object] = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "dataset_name": (
            provenance.dataset_name if provenance is not None else ""
        ),
        "dataset_version": (
            provenance.dataset_version if provenance is not None else ""
        ),
        "dataset_fingerprint": (
            provenance.dataset_fingerprint if provenance is not None else ""
        ),
        "benchmark_profile": (
            provenance.benchmark_profile if provenance is not None else ""
        ),
        "resolution_engine": (
            provenance.resolution_engine if provenance is not None else ""
        ),
        "provider": (
            provenance.provider if provenance is not None else ""
        ),
        "model": (
            provenance.model
            if provenance is not None and provenance.model is not None
            else ""
        ),
        "evaluator_version": (
            provenance.evaluator_version if provenance is not None else ""
        ),
        "git_sha": (
            provenance.git_sha if provenance is not None else ""
        ),
        "source_tree_dirty": (
            provenance.source_tree_dirty if provenance is not None else ""
        ),
        "total_dataset_records": result.total_dataset_records,
        "unique_dataset_records": result.unique_dataset_records,
        "duplicate_dataset_records": result.duplicate_dataset_records,
        "evaluated_cases": result.evaluated_cases,
        "failed_cases": failed_cases,
        "decision_accuracy": result.metrics.decision_accuracy,
        "credit_accuracy": result.metrics.credit_accuracy,
        "human_review_accuracy": result.metrics.human_review_accuracy,
    }

    write_header = not path.exists() or path.stat().st_size == 0

    with path.open(
        "a",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        if write_header:
            writer.writeheader()

        writer.writerow(row)
