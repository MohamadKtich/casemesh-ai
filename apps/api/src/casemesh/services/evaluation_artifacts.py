"""Read and validate persisted evaluation artifacts at runtime."""

import json
import os
from json import JSONDecodeError
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from casemesh.evaluation.stability import (
    StabilityEvaluation,
    canonical_json_hash,
)
from casemesh.schemas.evaluation import (
    EvaluationArtifactBundle,
    EvaluationFailuresArtifact,
    EvaluationResultsArtifact,
    EvaluationSummaryArtifact,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class EvaluationArtifactReadError(RuntimeError):
    """Raised when persisted evaluation evidence cannot be trusted."""


def resolve_evaluation_artifact_root() -> Path:
    """Resolve canonical evaluation artifact storage for this runtime."""

    configured = os.getenv(
        "EVALUATION_ARTIFACT_ROOT",
        "",
    ).strip()

    if configured:
        return Path(configured).expanduser().resolve()

    repository_root = Path(__file__).resolve().parents[5]

    return (
        repository_root
        / "data"
        / "evaluation"
        / "baseline-sla-v1"
    ).resolve()


class EvaluationArtifactReader:
    """Read-only access to committed benchmark evidence."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    @classmethod
    def from_environment(cls) -> "EvaluationArtifactReader":
        return cls(resolve_evaluation_artifact_root())

    def read_summary(self) -> EvaluationSummaryArtifact:
        return self._read_model(
            "evaluation_summary.json",
            EvaluationSummaryArtifact,
        )

    def read_results(self) -> EvaluationResultsArtifact:
        return self._read_model(
            "evaluation_results.json",
            EvaluationResultsArtifact,
        )

    def read_failures(self) -> EvaluationFailuresArtifact:
        return self._read_model(
            "evaluation_failures.json",
            EvaluationFailuresArtifact,
        )

    def read_stability(self) -> StabilityEvaluation:
        return self._read_model(
            "evaluation_stability.json",
            StabilityEvaluation,
        )

    def read_bundle(self) -> EvaluationArtifactBundle:
        """Read every JSON artifact and enforce cross-file integrity."""

        summary = self.read_summary()
        results = self.read_results()
        failures = self.read_failures()
        stability = self.read_stability()

        self._validate_consistency(
            summary=summary,
            results=results,
            failures=failures,
            stability=stability,
        )

        return EvaluationArtifactBundle(
            summary=summary,
            results=results,
            failures=failures,
            stability=stability,
        )

    def _read_model(
        self,
        filename: str,
        model_type: type[ModelT],
    ) -> ModelT:
        path = self.root / filename

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise EvaluationArtifactReadError(
                f"Unable to read evaluation artifact: {path}"
            ) from exc

        try:
            payload = json.loads(raw)
        except JSONDecodeError as exc:
            raise EvaluationArtifactReadError(
                f"Evaluation artifact contains invalid JSON: {path}"
            ) from exc

        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            raise EvaluationArtifactReadError(
                f"Evaluation artifact failed schema validation: {path}"
            ) from exc

    @staticmethod
    def _validate_consistency(
        *,
        summary: EvaluationSummaryArtifact,
        results: EvaluationResultsArtifact,
        failures: EvaluationFailuresArtifact,
        stability: StabilityEvaluation,
    ) -> None:
        run_ids = {
            summary.run_id,
            results.run_id,
            failures.run_id,
            stability.baseline_run_id,
        }

        if len(run_ids) != 1:
            raise EvaluationArtifactReadError(
                "Evaluation artifacts contain inconsistent run_id values."
            )

        if not (
            summary.created_at
            == results.created_at
            == failures.created_at
        ):
            raise EvaluationArtifactReadError(
                "Evaluation artifacts contain inconsistent timestamps."
            )

        if not (
            summary.provenance
            == results.provenance
            == failures.provenance
        ):
            raise EvaluationArtifactReadError(
                "Evaluation artifacts contain inconsistent provenance."
            )

        benchmark = results.benchmark
        dataset = summary.dataset

        expected_dataset_counts = (
            benchmark.total_dataset_records,
            benchmark.unique_dataset_records,
            benchmark.duplicate_dataset_records,
            benchmark.duplicate_groups,
        )
        recorded_dataset_counts = (
            dataset.total_records,
            dataset.unique_records,
            dataset.duplicate_records,
            dataset.duplicate_groups,
        )

        if recorded_dataset_counts != expected_dataset_counts:
            raise EvaluationArtifactReadError(
                "Evaluation summary dataset counts do not match results."
            )

        if summary.evaluated_cases != benchmark.evaluated_cases:
            raise EvaluationArtifactReadError(
                "Evaluation summary case count does not match results."
            )

        if summary.metrics != benchmark.metrics:
            raise EvaluationArtifactReadError(
                "Evaluation summary metrics do not match results."
            )

        if summary.failed_cases != failures.failed_cases:
            raise EvaluationArtifactReadError(
                "Evaluation failure counts are inconsistent."
            )

        if failures.failed_cases != len(failures.cases):
            raise EvaluationArtifactReadError(
                "Evaluation failure artifact count does not match cases."
            )

        if (
            stability.dataset_fingerprint
            != summary.provenance.dataset_fingerprint
        ):
            raise EvaluationArtifactReadError(
                "Stability evidence uses a different dataset fingerprint."
            )

        if (
            stability.baseline_source_git_sha
            != summary.provenance.git_sha
        ):
            raise EvaluationArtifactReadError(
                "Stability evidence uses a different baseline source SHA."
            )

        benchmark_hash = canonical_json_hash(
            benchmark.model_dump(mode="json")
        )

        if benchmark_hash != stability.baseline_benchmark_hash:
            raise EvaluationArtifactReadError(
                "Stability baseline hash does not match evaluation results."
            )
