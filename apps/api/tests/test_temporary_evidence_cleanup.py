from uuid import UUID

import pytest

from casemesh.intelligence.staging import (
    StagedEvidenceObject,
    TemporaryEvidenceRequest,
)
from casemesh.intelligence.staging_scope import (
    managed_temporary_evidence,
)


class RecordingStager:
    def __init__(
        self,
        *,
        stage_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self.stage_error = stage_error
        self.delete_error = delete_error
        self.stage_calls = 0
        self.delete_calls = 0

    async def stage(
        self,
        request: TemporaryEvidenceRequest,
    ) -> StagedEvidenceObject:
        self.stage_calls += 1

        if self.stage_error is not None:
            raise self.stage_error

        return StagedEvidenceObject(
            provider="test",
            bucket="temporary-test-bucket",
            object_key=f"casemesh-temp/{request.document_id}",
            sha256="a" * 64,
            size_bytes=len(request.content),
            content_type=request.content_type,
        )

    async def delete(
        self,
        staged: StagedEvidenceObject,
    ) -> None:
        self.delete_calls += 1

        if self.delete_error is not None:
            raise self.delete_error

    async def health(self) -> dict[str, object]:
        return {
            "provider": "test",
            "network_checked": False,
        }


def _request() -> TemporaryEvidenceRequest:
    return TemporaryEvidenceRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        document_id=UUID("33333333-3333-3333-3333-333333333333"),
        content=b"synthetic temporary evidence",
        content_type="application/pdf",
    )


@pytest.mark.asyncio
async def test_cleanup_occurs_after_successful_processing() -> None:
    stager = RecordingStager()

    async with managed_temporary_evidence(
        stager=stager,
        request=_request(),
    ) as staged:
        assert staged.temporary is True

    assert stager.stage_calls == 1
    assert stager.delete_calls == 1


@pytest.mark.asyncio
async def test_cleanup_occurs_when_processing_fails() -> None:
    stager = RecordingStager()

    with pytest.raises(
        RuntimeError,
        match="processing failed",
    ):
        async with managed_temporary_evidence(
            stager=stager,
            request=_request(),
        ):
            raise RuntimeError("processing failed")

    assert stager.stage_calls == 1
    assert stager.delete_calls == 1


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_mask_processing_error() -> None:
    stager = RecordingStager(
        delete_error=RuntimeError("cleanup failed"),
    )

    with pytest.raises(
        ValueError,
        match="primary processing failure",
    ) as exc_info:
        async with managed_temporary_evidence(
            stager=stager,
            request=_request(),
        ):
            raise ValueError("primary processing failure")

    notes = getattr(
        exc_info.value,
        "__notes__",
        [],
    )

    assert any("cleanup failed" in note for note in notes)

    assert stager.delete_calls == 1


@pytest.mark.asyncio
async def test_cleanup_failure_propagates_after_success() -> None:
    stager = RecordingStager(
        delete_error=RuntimeError("cleanup failed"),
    )

    with pytest.raises(
        RuntimeError,
        match="cleanup failed",
    ):
        async with managed_temporary_evidence(
            stager=stager,
            request=_request(),
        ):
            pass

    assert stager.delete_calls == 1


@pytest.mark.asyncio
async def test_stage_failure_does_not_attempt_delete() -> None:
    stager = RecordingStager(
        stage_error=RuntimeError("stage failed"),
    )

    with pytest.raises(
        RuntimeError,
        match="stage failed",
    ):
        async with managed_temporary_evidence(
            stager=stager,
            request=_request(),
        ):
            pass

    assert stager.stage_calls == 1
    assert stager.delete_calls == 0
