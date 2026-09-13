import sys
from uuid import UUID

import pytest

from casemesh.integrations.aws.textract import (
    MockTextractDocumentIntelligence,
    TextractResponseParser,
)
from casemesh.intelligence.document_intelligence import (
    DocumentIntelligenceJob,
    DocumentIntelligenceRequest,
    DocumentTextLine,
)
from casemesh.intelligence.staging import StagedEvidenceObject


def _staged() -> StagedEvidenceObject:
    return StagedEvidenceObject(
        provider="aws-s3-mock",
        bucket="synthetic-textract-bucket",
        object_key=(
            "casemesh-temp/"
            "11111111-1111-1111-1111-111111111111/"
            "22222222-2222-2222-2222-222222222222/"
            "33333333-3333-3333-3333-333333333333/" + ("a" * 64)
        ),
        sha256="a" * 64,
        size_bytes=100,
        content_type="application/pdf",
    )


def _request() -> DocumentIntelligenceRequest:
    return DocumentIntelligenceRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        document_id=UUID("33333333-3333-3333-3333-333333333333"),
        staged=_staged(),
    )


def test_document_text_line_validates_page_number() -> None:
    with pytest.raises(
        ValueError,
        match="page_number",
    ):
        DocumentTextLine(
            page_number=0,
            text="synthetic",
        )


def test_document_text_line_rejects_blank_text() -> None:
    with pytest.raises(
        ValueError,
        match="must not be blank",
    ):
        DocumentTextLine(
            page_number=1,
            text=" ",
        )


def test_document_text_line_validates_confidence() -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 100",
    ):
        DocumentTextLine(
            page_number=1,
            text="synthetic",
            confidence=101.0,
        )


def test_document_intelligence_request_requires_temporary_staging() -> None:
    permanent = StagedEvidenceObject(
        provider="test",
        bucket="bucket",
        object_key="object",
        sha256="a" * 64,
        size_bytes=10,
        content_type="application/pdf",
        temporary=False,
    )

    with pytest.raises(
        ValueError,
        match="temporary staged object",
    ):
        DocumentIntelligenceRequest(
            case_id=UUID("11111111-1111-1111-1111-111111111111"),
            investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
            document_id=UUID("33333333-3333-3333-3333-333333333333"),
            staged=permanent,
        )


def test_document_job_rejects_blank_job_id() -> None:
    with pytest.raises(
        ValueError,
        match="job_id",
    ):
        DocumentIntelligenceJob(
            provider="test",
            job_id=" ",
            status="in_progress",
        )


def test_textract_parser_normalizes_succeeded_response() -> None:
    parser = TextractResponseParser()

    result = parser.parse(
        job_id="synthetic-job",
        response={
            "JobStatus": "SUCCEEDED",
            "DocumentMetadata": {
                "Pages": 2,
            },
            "Blocks": [
                {
                    "BlockType": "LINE",
                    "Page": 1,
                    "Text": "First line",
                    "Confidence": 99.5,
                },
                {
                    "BlockType": "WORD",
                    "Page": 1,
                    "Text": "Ignored",
                    "Confidence": 98.0,
                },
                {
                    "BlockType": "LINE",
                    "Page": 2,
                    "Text": "Second line",
                    "Confidence": 97.25,
                },
            ],
        },
    )

    assert result.provider == "aws-textract"
    assert result.job_id == "synthetic-job"
    assert result.status == "succeeded"
    assert result.page_count == 2
    assert result.text == "First line\nSecond line"

    assert result.lines == (
        DocumentTextLine(
            page_number=1,
            text="First line",
            confidence=99.5,
        ),
        DocumentTextLine(
            page_number=2,
            text="Second line",
            confidence=97.25,
        ),
    )


def test_textract_parser_normalizes_in_progress_response() -> None:
    result = TextractResponseParser().parse(
        job_id="synthetic-job",
        response={
            "JobStatus": "IN_PROGRESS",
        },
    )

    assert result.status == "in_progress"
    assert result.text == ""
    assert result.lines == ()
    assert result.page_count == 0


def test_textract_parser_normalizes_failed_response() -> None:
    result = TextractResponseParser().parse(
        job_id="synthetic-job",
        response={
            "JobStatus": "FAILED",
        },
    )

    assert result.status == "failed"
    assert result.text == ""
    assert result.lines == ()


def test_textract_parser_marks_partial_success() -> None:
    result = TextractResponseParser().parse(
        job_id="synthetic-job",
        response={
            "JobStatus": "PARTIAL_SUCCESS",
            "DocumentMetadata": {
                "Pages": 1,
            },
            "Blocks": [
                {
                    "BlockType": "LINE",
                    "Page": 1,
                    "Text": "Partial line",
                    "Confidence": 90.0,
                },
            ],
        },
    )

    assert result.status == "succeeded"
    assert result.text == "Partial line"
    assert result.warnings == ("PARTIAL_SUCCESS",)


def test_textract_parser_rejects_unknown_status() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported Textract JobStatus",
    ):
        TextractResponseParser().parse(
            job_id="synthetic-job",
            response={
                "JobStatus": "UNKNOWN",
            },
        )


def test_textract_parser_rejects_missing_status() -> None:
    with pytest.raises(
        ValueError,
        match="missing JobStatus",
    ):
        TextractResponseParser().parse(
            job_id="synthetic-job",
            response={},
        )


@pytest.mark.asyncio
async def test_mock_textract_job_is_deterministic() -> None:
    provider = MockTextractDocumentIntelligence()
    request = _request()

    first = await provider.start(request)
    second = await provider.start(request)

    assert first == second
    assert first.status == "in_progress"
    assert first.provider == "aws-textract-mock"
    assert len(first.job_id) == 64


@pytest.mark.asyncio
async def test_mock_textract_returns_normalized_success() -> None:
    provider = MockTextractDocumentIntelligence(
        extracted_text="Synthetic extracted evidence",
        confidence=98.5,
    )

    job = await provider.start(_request())
    result = await provider.get(job.job_id)

    assert result.status == "succeeded"
    assert result.text == "Synthetic extracted evidence"
    assert result.page_count == 1

    assert result.lines == (
        DocumentTextLine(
            page_number=1,
            text="Synthetic extracted evidence",
            confidence=98.5,
        ),
    )


@pytest.mark.asyncio
async def test_mock_textract_can_model_failure() -> None:
    provider = MockTextractDocumentIntelligence(
        fail_jobs=True,
    )

    job = await provider.start(_request())
    result = await provider.get(job.job_id)

    assert result.status == "failed"
    assert result.text == ""
    assert result.lines == ()
    assert result.warnings == ("SYNTHETIC_FAILURE",)


@pytest.mark.asyncio
async def test_mock_textract_rejects_unknown_job() -> None:
    provider = MockTextractDocumentIntelligence()

    with pytest.raises(
        ValueError,
        match="Unknown mock Textract job_id",
    ):
        await provider.get("missing-job")


@pytest.mark.asyncio
async def test_mock_textract_health_is_offline() -> None:
    sys.modules.pop("boto3", None)

    provider = MockTextractDocumentIntelligence()

    health = await provider.health()

    assert health["provider"] == "aws-textract-mock"
    assert health["network_checked"] is False
    assert health["job_count"] == 0
    assert "boto3" not in sys.modules
