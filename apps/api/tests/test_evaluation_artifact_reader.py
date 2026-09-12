import json
import shutil
from pathlib import Path

import pytest

from casemesh.services.evaluation_artifacts import (
    EvaluationArtifactReader,
    EvaluationArtifactReadError,
    resolve_evaluation_artifact_root,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _canonical_root() -> Path:
    return (
        _repo_root()
        / "data"
        / "evaluation"
        / "baseline-sla-v1"
    )


def _copy_json_artifacts(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    for name in (
        "evaluation_summary.json",
        "evaluation_results.json",
        "evaluation_failures.json",
        "evaluation_stability.json",
    ):
        shutil.copy2(
            _canonical_root() / name,
            destination / name,
        )


def test_environment_root_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "EVALUATION_ARTIFACT_ROOT",
        str(tmp_path),
    )

    assert resolve_evaluation_artifact_root() == tmp_path.resolve()


def test_reader_loads_real_committed_bundle() -> None:
    reader = EvaluationArtifactReader(_canonical_root())

    bundle = reader.read_bundle()

    assert bundle.summary.run_id == "sla-deterministic-dataset-v1"
    assert bundle.summary.dataset.total_records == 100
    assert bundle.summary.dataset.unique_records == 10
    assert bundle.summary.dataset.duplicate_records == 90
    assert bundle.summary.evaluated_cases == 10
    assert bundle.summary.failed_cases == 0
    assert len(bundle.results.benchmark.cases) == 10
    assert bundle.failures.cases == []
    assert bundle.stability.repeated_runs == 20
    assert bundle.stability.total_case_executions == 200
    assert bundle.stability.unique_result_hashes == 1
    assert bundle.stability.stable is True


def test_reader_rejects_missing_artifact(tmp_path: Path) -> None:
    reader = EvaluationArtifactReader(tmp_path)

    with pytest.raises(
        EvaluationArtifactReadError,
        match="Unable to read",
    ):
        reader.read_summary()


def test_reader_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "evaluation_summary.json"
    path.write_text("{invalid", encoding="utf-8")

    reader = EvaluationArtifactReader(tmp_path)

    with pytest.raises(
        EvaluationArtifactReadError,
        match="invalid JSON",
    ):
        reader.read_summary()


def test_reader_rejects_cross_artifact_run_mismatch(
    tmp_path: Path,
) -> None:
    _copy_json_artifacts(tmp_path)

    summary_path = tmp_path / "evaluation_summary.json"
    payload = json.loads(
        summary_path.read_text(encoding="utf-8")
    )
    payload["run_id"] = "different-run"
    summary_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    reader = EvaluationArtifactReader(tmp_path)

    with pytest.raises(
        EvaluationArtifactReadError,
        match="run_id",
    ):
        reader.read_bundle()


def test_reader_rejects_stability_hash_mismatch(
    tmp_path: Path,
) -> None:
    _copy_json_artifacts(tmp_path)

    stability_path = tmp_path / "evaluation_stability.json"
    payload = json.loads(
        stability_path.read_text(encoding="utf-8")
    )
    payload["baseline_benchmark_hash"] = "0" * 64
    stability_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    reader = EvaluationArtifactReader(tmp_path)

    with pytest.raises(
        EvaluationArtifactReadError,
        match="baseline hash",
    ):
        reader.read_bundle()
