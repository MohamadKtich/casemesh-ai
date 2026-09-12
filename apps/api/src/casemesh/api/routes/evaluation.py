"""Read-only REST endpoints for persisted evaluation evidence."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from casemesh.evaluation.runner import BenchmarkCaseResult
from casemesh.evaluation.stability import StabilityEvaluation
from casemesh.schemas.evaluation import (
    EvaluationArtifactBundle,
    EvaluationFailuresArtifact,
    EvaluationSummaryArtifact,
)
from casemesh.services.evaluation_artifacts import (
    EvaluationArtifactReader,
    EvaluationArtifactReadError,
)

router = APIRouter(
    prefix="/evaluation",
    tags=["evaluation"],
)


def get_evaluation_reader() -> EvaluationArtifactReader:
    """Provide read-only access to packaged evaluation evidence."""

    return EvaluationArtifactReader.from_environment()


EvaluationReaderDep = Annotated[
    EvaluationArtifactReader,
    Depends(get_evaluation_reader),
]


def _read_validated_bundle(
    reader: EvaluationArtifactReader,
) -> EvaluationArtifactBundle:
    """Read all evidence and translate integrity failures to HTTP 503."""

    try:
        return reader.read_bundle()
    except EvaluationArtifactReadError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Evaluation artifacts are unavailable or failed "
                "integrity validation."
            ),
        ) from exc


@router.get(
    "/summary",
    response_model=EvaluationSummaryArtifact,
)
async def evaluation_summary(
    reader: EvaluationReaderDep,
) -> EvaluationSummaryArtifact:
    """Return benchmark summary metrics and provenance."""

    return _read_validated_bundle(reader).summary


@router.get(
    "/stability",
    response_model=StabilityEvaluation,
)
async def evaluation_stability(
    reader: EvaluationReaderDep,
) -> StabilityEvaluation:
    """Return repeated-run deterministic stability evidence."""

    return _read_validated_bundle(reader).stability


@router.get(
    "/cases",
    response_model=list[BenchmarkCaseResult],
)
async def evaluation_cases(
    reader: EvaluationReaderDep,
) -> list[BenchmarkCaseResult]:
    """Return results for the unique evaluated benchmark scenarios."""

    return _read_validated_bundle(reader).results.benchmark.cases


@router.get(
    "/failures",
    response_model=EvaluationFailuresArtifact,
)
async def evaluation_failures(
    reader: EvaluationReaderDep,
) -> EvaluationFailuresArtifact:
    """Return failed benchmark cases, if any."""

    return _read_validated_bundle(reader).failures
