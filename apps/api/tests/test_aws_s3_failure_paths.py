from uuid import UUID

import pytest

from casemesh.integrations.aws.staging import (
    S3TemporaryEvidenceStager,
)
from casemesh.intelligence.staging import (
    TemporaryEvidenceRequest,
)
from casemesh.intelligence.staging_scope import (
    managed_temporary_evidence,
)


class FailureS3Client:
    def __init__(
        self,
        *,
        put_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self.put_error = put_error
        self.delete_error = delete_error
        self.put_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []

    def put_object(
        self,
        **kwargs: object,
    ) -> object:
        self.put_calls.append(dict(kwargs))

        if self.put_error is not None:
            raise self.put_error

        return {
            "ETag": '"synthetic"',
        }

    def delete_object(
        self,
        **kwargs: object,
    ) -> object:
        self.delete_calls.append(dict(kwargs))

        if self.delete_error is not None:
            raise self.delete_error

        return {}


def _request() -> TemporaryEvidenceRequest:
    return TemporaryEvidenceRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        document_id=UUID("33333333-3333-3333-3333-333333333333"),
        content=b"synthetic failure-path evidence",
        content_type="application/pdf",
    )


@pytest.mark.asyncio
async def test_put_failure_propagates_without_delete_attempt() -> None:
    client = FailureS3Client(
        put_error=RuntimeError("synthetic put failure"),
    )

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic put failure",
    ):
        await stager.stage(_request())

    assert len(client.put_calls) == 1
    assert client.delete_calls == []


@pytest.mark.asyncio
async def test_delete_failure_propagates_after_successful_stage() -> None:
    client = FailureS3Client(
        delete_error=RuntimeError("synthetic delete failure"),
    )

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    staged = await stager.stage(_request())

    with pytest.raises(
        RuntimeError,
        match="synthetic delete failure",
    ):
        await stager.delete(staged)

    assert len(client.put_calls) == 1
    assert len(client.delete_calls) == 1


@pytest.mark.asyncio
async def test_processing_error_survives_real_adapter_cleanup_failure() -> None:
    client = FailureS3Client(
        delete_error=RuntimeError("synthetic cleanup failure"),
    )

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
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

    assert any("synthetic cleanup failure" in note for note in notes)

    assert len(client.put_calls) == 1
    assert len(client.delete_calls) == 1


@pytest.mark.asyncio
async def test_successful_processing_surfaces_real_cleanup_failure() -> None:
    client = FailureS3Client(
        delete_error=RuntimeError("synthetic cleanup failure"),
    )

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic cleanup failure",
    ):
        async with managed_temporary_evidence(
            stager=stager,
            request=_request(),
        ):
            pass

    assert len(client.put_calls) == 1
    assert len(client.delete_calls) == 1
