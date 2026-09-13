import hashlib
from uuid import UUID

import pytest

from casemesh.integrations.aws.staging import (
    MockS3TemporaryEvidenceStager,
    S3TemporaryEvidenceKeyBuilder,
)
from casemesh.intelligence.staging import TemporaryEvidenceRequest


def _request(
    *,
    content: bytes = b"synthetic evidence",
) -> TemporaryEvidenceRequest:
    return TemporaryEvidenceRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        document_id=UUID("33333333-3333-3333-3333-333333333333"),
        content=content,
        content_type="application/pdf",
    )


def test_temporary_request_rejects_empty_content() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        TemporaryEvidenceRequest(
            case_id=UUID("11111111-1111-1111-1111-111111111111"),
            investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
            document_id=UUID("33333333-3333-3333-3333-333333333333"),
            content=b"",
            content_type="application/pdf",
        )


def test_temporary_request_rejects_blank_content_type() -> None:
    with pytest.raises(
        ValueError,
        match="content_type",
    ):
        TemporaryEvidenceRequest(
            case_id=UUID("11111111-1111-1111-1111-111111111111"),
            investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
            document_id=UUID("33333333-3333-3333-3333-333333333333"),
            content=b"synthetic evidence",
            content_type="   ",
        )


def test_key_builder_is_deterministic_and_isolated() -> None:
    request = _request()
    digest = hashlib.sha256(request.content).hexdigest()

    builder = S3TemporaryEvidenceKeyBuilder()

    first = builder.build(
        request=request,
        sha256=digest,
    )

    second = builder.build(
        request=request,
        sha256=digest,
    )

    assert first == second

    assert first == (
        "casemesh-temp/"
        "11111111-1111-1111-1111-111111111111/"
        "22222222-2222-2222-2222-222222222222/"
        "33333333-3333-3333-3333-333333333333/"
        f"{digest}"
    )


def test_key_policy_contains_no_user_filename() -> None:
    request = _request()
    digest = hashlib.sha256(request.content).hexdigest()

    key = S3TemporaryEvidenceKeyBuilder().build(
        request=request,
        sha256=digest,
    )

    assert "invoice.pdf" not in key
    assert "\\" not in key
    assert ".." not in key
    assert key.startswith("casemesh-temp/")


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        " ",
        "../unsafe",
        "unsafe/../prefix",
        "unsafe//prefix",
    ],
)
def test_key_builder_rejects_unsafe_prefixes(
    prefix: str,
) -> None:
    with pytest.raises(ValueError):
        S3TemporaryEvidenceKeyBuilder(
            prefix=prefix,
        )


@pytest.mark.asyncio
async def test_mock_stage_returns_content_addressed_reference() -> None:
    request = _request()
    expected_digest = hashlib.sha256(request.content).hexdigest()

    stager = MockS3TemporaryEvidenceStager()

    staged = await stager.stage(request)

    assert staged.provider == "aws-s3-mock"
    assert staged.bucket == "casemesh-temporary-evidence-mock"
    assert staged.sha256 == expected_digest
    assert staged.size_bytes == len(request.content)
    assert staged.content_type == "application/pdf"
    assert staged.temporary is True
    assert staged.object_key.endswith(expected_digest)


@pytest.mark.asyncio
async def test_mock_stage_is_idempotent_for_same_request() -> None:
    stager = MockS3TemporaryEvidenceStager()
    request = _request()

    first = await stager.stage(request)
    second = await stager.stage(request)

    assert first == second

    health = await stager.health()

    assert health["object_count"] == 1


@pytest.mark.asyncio
async def test_different_content_produces_different_object_key() -> None:
    stager = MockS3TemporaryEvidenceStager()

    first = await stager.stage(
        _request(
            content=b"first synthetic evidence",
        )
    )

    second = await stager.stage(
        _request(
            content=b"second synthetic evidence",
        )
    )

    assert first.sha256 != second.sha256
    assert first.object_key != second.object_key


@pytest.mark.asyncio
async def test_mock_delete_is_idempotent() -> None:
    stager = MockS3TemporaryEvidenceStager()
    staged = await stager.stage(_request())

    health_before = await stager.health()

    assert health_before["object_count"] == 1

    await stager.delete(staged)
    await stager.delete(staged)

    health_after = await stager.health()

    assert health_after["object_count"] == 0


@pytest.mark.asyncio
async def test_mock_health_never_claims_network_validation() -> None:
    stager = MockS3TemporaryEvidenceStager()

    health = await stager.health()

    assert health["provider"] == "aws-s3-mock"
    assert health["network_checked"] is False
    assert health["temporary"] is True
    assert health["object_count"] == 0


@pytest.mark.asyncio
async def test_delete_refuses_different_bucket() -> None:
    first_stager = MockS3TemporaryEvidenceStager(
        bucket="bucket-a",
    )

    second_stager = MockS3TemporaryEvidenceStager(
        bucket="bucket-b",
    )

    staged = await first_stager.stage(_request())

    with pytest.raises(
        ValueError,
        match="different bucket",
    ):
        await second_stager.delete(staged)
