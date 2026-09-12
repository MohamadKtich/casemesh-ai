"""Typed schemas for persisted evaluation artifacts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from casemesh.evaluation.artifacts import EvaluationRunProvenance
from casemesh.evaluation.metrics import EvaluationMetricSummary
from casemesh.evaluation.runner import (
    BenchmarkCaseResult,
    BenchmarkRunResult,
)
from casemesh.evaluation.stability import StabilityEvaluation


class EvaluationArtifactMetadata(BaseModel):
    """Metadata shared by persisted benchmark JSON artifacts."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    created_at: datetime
    provenance: EvaluationRunProvenance

    @field_validator("created_at")
    @classmethod
    def require_timezone_aware_created_at(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware.")

        return value


class EvaluationDatasetSummary(BaseModel):
    """Dataset counts recorded with one benchmark run."""

    model_config = ConfigDict(extra="forbid")

    total_records: int = Field(ge=0)
    unique_records: int = Field(ge=0)
    duplicate_records: int = Field(ge=0)
    duplicate_groups: int = Field(ge=0)


class EvaluationSummaryArtifact(EvaluationArtifactMetadata):
    """Typed representation of evaluation_summary.json."""

    dataset: EvaluationDatasetSummary
    evaluated_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    metrics: EvaluationMetricSummary


class EvaluationResultsArtifact(EvaluationArtifactMetadata):
    """Typed representation of evaluation_results.json."""

    benchmark: BenchmarkRunResult


class EvaluationFailuresArtifact(EvaluationArtifactMetadata):
    """Typed representation of evaluation_failures.json."""

    failed_cases: int = Field(ge=0)
    cases: list[BenchmarkCaseResult]


class EvaluationArtifactBundle(BaseModel):
    """Validated persisted evidence consumed by the Evaluation API."""

    model_config = ConfigDict(extra="forbid")

    summary: EvaluationSummaryArtifact
    results: EvaluationResultsArtifact
    failures: EvaluationFailuresArtifact
    stability: StabilityEvaluation
