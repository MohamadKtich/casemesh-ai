"""Repeated-run stability evaluation for deterministic benchmarks."""

import hashlib
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from casemesh.evaluation.dataset import BenchmarkDataset
from casemesh.evaluation.runner import BenchmarkRunResult
from casemesh.evaluation.sla_adapter import run_sla_dataset_benchmark


class StabilityRunSample(BaseModel):
    """One repeated deterministic benchmark execution."""

    model_config = ConfigDict(extra="forbid")

    run_index: int = Field(ge=1)
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    duration_ms: float = Field(ge=0)


class StabilityEvaluation(BaseModel):
    """Persistent evidence of deterministic benchmark repeatability."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    created_at: datetime
    baseline_run_id: str = Field(min_length=1)
    dataset_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_source_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    stability_evaluator_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree_dirty: bool
    repeated_runs: int = Field(ge=1)
    unique_scenarios_per_run: int = Field(ge=1)
    total_case_executions: int = Field(ge=1)
    unique_result_hashes: int = Field(ge=1)
    unique_result_hash_values: list[str]
    baseline_benchmark_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    repeated_result_hash: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    decision_stability: float = Field(ge=0, le=1)
    credit_stability: float = Field(ge=0, le=1)
    human_review_stability: float = Field(ge=0, le=1)
    stable: bool
    timing_scope: Literal["local_diagnostic_only"] = (
        "local_diagnostic_only"
    )
    latency_min_ms: float = Field(ge=0)
    latency_mean_ms: float = Field(ge=0)
    latency_p95_ms: float = Field(ge=0)
    latency_max_ms: float = Field(ge=0)
    samples: list[StabilityRunSample]

    @field_validator("created_at")
    @classmethod
    def require_timezone_aware_timestamp(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware.")
        return value


def canonical_json_hash(payload: object) -> str:
    """Return SHA-256 of canonical JSON content."""

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def evaluate_repeatability(
    *,
    dataset: BenchmarkDataset,
    dataset_root: Path,
    baseline_result: BenchmarkRunResult,
    dataset_fingerprint: str,
    baseline_run_id: str,
    baseline_source_git_sha: str,
    stability_evaluator_git_sha: str,
    source_tree_dirty: bool,
    repeated_runs: int = 20,
) -> StabilityEvaluation:
    """Execute and compare repeated deterministic benchmark runs."""

    if repeated_runs < 1:
        raise ValueError("repeated_runs must be at least 1.")

    baseline_hash = canonical_json_hash(
        baseline_result.model_dump(mode="json")
    )

    result_hashes: list[str] = []
    durations_ms: list[float] = []
    samples: list[StabilityRunSample] = []
    decision_matches = 0
    credit_matches = 0
    review_matches = 0

    for run_index in range(1, repeated_runs + 1):
        started = time.perf_counter()

        result = run_sla_dataset_benchmark(
            dataset=dataset,
            dataset_root=dataset_root,
        )

        duration_ms = (time.perf_counter() - started) * 1000
        result_hash = canonical_json_hash(
            result.model_dump(mode="json")
        )

        result_hashes.append(result_hash)
        durations_ms.append(duration_ms)
        samples.append(
            StabilityRunSample(
                run_index=run_index,
                result_hash=result_hash,
                duration_ms=duration_ms,
            )
        )

        decision_matches += int(
            result.metrics.decision_accuracy
            == baseline_result.metrics.decision_accuracy
        )
        credit_matches += int(
            result.metrics.credit_accuracy
            == baseline_result.metrics.credit_accuracy
        )
        review_matches += int(
            result.metrics.human_review_accuracy
            == baseline_result.metrics.human_review_accuracy
        )

    unique_hashes = sorted(set(result_hashes))
    repeated_result_hash = (
        unique_hashes[0] if len(unique_hashes) == 1 else None
    )

    stable = (
        len(unique_hashes) == 1
        and repeated_result_hash == baseline_hash
    )

    sorted_durations = sorted(durations_ms)
    p95_index = min(
        len(sorted_durations) - 1,
        max(0, int(len(sorted_durations) * 0.95) - 1),
    )

    return StabilityEvaluation(
        created_at=datetime.now(UTC),
        baseline_run_id=baseline_run_id,
        dataset_fingerprint=dataset_fingerprint,
        baseline_source_git_sha=baseline_source_git_sha,
        stability_evaluator_git_sha=stability_evaluator_git_sha,
        source_tree_dirty=source_tree_dirty,
        repeated_runs=repeated_runs,
        unique_scenarios_per_run=dataset.unique_records,
        total_case_executions=(
            repeated_runs * dataset.unique_records
        ),
        unique_result_hashes=len(unique_hashes),
        unique_result_hash_values=unique_hashes,
        baseline_benchmark_hash=baseline_hash,
        repeated_result_hash=repeated_result_hash,
        decision_stability=decision_matches / repeated_runs,
        credit_stability=credit_matches / repeated_runs,
        human_review_stability=review_matches / repeated_runs,
        stable=stable,
        latency_min_ms=min(durations_ms),
        latency_mean_ms=statistics.mean(durations_ms),
        latency_p95_ms=sorted_durations[p95_index],
        latency_max_ms=max(durations_ms),
        samples=samples,
    )


def write_stability_artifact(
    *,
    result: StabilityEvaluation,
    path: Path,
) -> None:
    """Persist stability evidence as deterministic JSON structure."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
