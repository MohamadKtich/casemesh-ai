from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from casemesh.intelligence.staging import (
    StagedEvidenceObject,
    TemporaryEvidenceRequest,
    TemporaryEvidenceStager,
)


@asynccontextmanager
async def managed_temporary_evidence(
    *,
    stager: TemporaryEvidenceStager,
    request: TemporaryEvidenceRequest,
) -> AsyncIterator[StagedEvidenceObject]:
    """Stage evidence and guarantee a cleanup attempt when processing ends.

    If processing already failed, a cleanup failure is attached as a note to
    the original exception instead of replacing the primary failure.
    """

    staged = await stager.stage(request)
    processing_error: BaseException | None = None

    try:
        yield staged
    except BaseException as exc:  # noqa: BLE001
        processing_error = exc
        raise
    finally:
        try:
            await stager.delete(staged)
        except Exception as cleanup_error:  # noqa: BLE001
            if processing_error is None:
                raise

            processing_error.add_note(
                "Temporary evidence cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
