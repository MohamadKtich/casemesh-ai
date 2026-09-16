import re
import sys
from uuid import UUID

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws import (
    AWSIntelligenceGateway,
    build_aws_intelligence_gateway,
)
from casemesh.integrations.aws.textract import (
    MockTextractDocumentIntelligence,
    TextractDocumentIntelligence,
    build_aws_document_intelligence_provider,
)
from casemesh.intelligence.document_intelligence import (
    DocumentIntelligenceRequest,
)
from casemesh.intelligence.staging import StagedEvidenceObject


class FakeTextractClient:
    def __init__(
        self,
        *,
        start_response: object | None = None,
        get_response: object | None = None,
    ) -> None:
        self.start_response = (
            start_response
            if start_response is not None
            else {
                "JobId": "synthetic-job-id",
            }
        )

        self.get_response = (
            get_response
            if get_response is not None
            else {
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": {
                    "Pages": 1,
                },
                "Blocks": [
                    {
                        "BlockType": "LINE",
                        "Page": 1,
                        "Text": "Extracted synthetic line",
                        "Confidence": 99.0,
                    }
                ],
            }
        )

        self.start_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []

    def start_document_text_detection(
        self,
        **kwargs: object,
    ) -> object:
        self.start_calls.append(dict(kwargs))
        return self.start_response

    def get_document_text_detection(
        self,
        **kwargs: object,
    ) -> object:
        self.get_calls.append(dict(kwargs))
        return self.get_response


class FakeTextractClientFactory:
    def __init__(
        self,
        client: FakeTextractClient,
    ) -> None:
        self.client = client
        self.calls: list[tuple[str, str]] = []

    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        self.calls.append(
            (
                service_name,
                region_name,
            )
        )

        return self.client


def _staged(
    *,
    provider: str = "aws-s3",
) -> StagedEvidenceObject:
    return StagedEvidenceObject(
        provider=provider,
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


def _request(
    *,
    provider: str = "aws-s3",
) -> DocumentIntelligenceRequest:
    return DocumentIntelligenceRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        document_id=UUID("33333333-3333-3333-3333-333333333333"),
        staged=_staged(
            provider=provider,
        ),
    )


def _settings(
    *,
    mode: str,
) -> Settings:
    return Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode=mode,
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket="synthetic-textract-bucket",
        aws_textract_completion_topic_arn="synthetic-topic",
        aws_textract_notification_role_arn="arn:aws:iam::123456789012:role/CaseMeshTextractNotificationRole",
        aws_textract_queue_url="synthetic-queue",
    )


@pytest.mark.asyncio
async def test_real_adapter_starts_textract_with_s3_location() -> None:
    client = FakeTextractClient()

    provider = TextractDocumentIntelligence(
        client=client,
    )

    job = await provider.start(_request())

    assert job.provider == "aws-textract"
    assert job.job_id == "synthetic-job-id"
    assert job.status == "in_progress"

    assert len(client.start_calls) == 1

    call = client.start_calls[0]

    assert call["DocumentLocation"] == {
        "S3Object": {
            "Bucket": "synthetic-textract-bucket",
            "Name": _staged().object_key,
        }
    }


@pytest.mark.asyncio
async def test_start_uses_deterministic_idempotency_token() -> None:
    client = FakeTextractClient()

    provider = TextractDocumentIntelligence(
        client=client,
    )

    request = _request()

    await provider.start(request)
    await provider.start(request)

    first_token = client.start_calls[0]["ClientRequestToken"]
    second_token = client.start_calls[1]["ClientRequestToken"]

    assert first_token == second_token
    assert isinstance(first_token, str)
    assert len(first_token) == 64
    assert re.fullmatch(
        r"[a-f0-9]{64}",
        first_token,
    )


@pytest.mark.asyncio
async def test_idempotency_token_changes_with_object_identity() -> None:
    first_client = FakeTextractClient()
    second_client = FakeTextractClient()

    first_provider = TextractDocumentIntelligence(
        client=first_client,
    )

    second_provider = TextractDocumentIntelligence(
        client=second_client,
    )

    first_request = _request()

    different_object = StagedEvidenceObject(
        provider="aws-s3",
        bucket="synthetic-textract-bucket",
        object_key="casemesh-temp/different-object",
        sha256="b" * 64,
        size_bytes=100,
        content_type="application/pdf",
    )

    second_request = DocumentIntelligenceRequest(
        case_id=first_request.case_id,
        investigation_run_id=first_request.investigation_run_id,
        document_id=first_request.document_id,
        staged=different_object,
    )

    await first_provider.start(first_request)
    await second_provider.start(second_request)

    assert (
        first_client.start_calls[0]["ClientRequestToken"]
        != second_client.start_calls[0]["ClientRequestToken"]
    )


@pytest.mark.asyncio
async def test_real_adapter_rejects_non_s3_staging() -> None:
    client = FakeTextractClient()

    provider = TextractDocumentIntelligence(
        client=client,
    )

    with pytest.raises(
        ValueError,
        match="staged by aws-s3",
    ):
        await provider.start(
            _request(
                provider="aws-s3-mock",
            )
        )

    assert client.start_calls == []


@pytest.mark.asyncio
async def test_real_adapter_requires_job_id_from_start_response() -> None:
    client = FakeTextractClient(
        start_response={},
    )

    provider = TextractDocumentIntelligence(
        client=client,
    )

    with pytest.raises(
        ValueError,
        match="missing JobId",
    ):
        await provider.start(_request())


@pytest.mark.asyncio
async def test_real_adapter_rejects_invalid_start_response_shape() -> None:
    client = FakeTextractClient(
        start_response="not-a-mapping",
    )

    provider = TextractDocumentIntelligence(
        client=client,
    )

    with pytest.raises(
        ValueError,
        match="invalid response",
    ):
        await provider.start(_request())


@pytest.mark.asyncio
async def test_real_adapter_gets_single_page_result() -> None:
    client = FakeTextractClient()

    provider = TextractDocumentIntelligence(
        client=client,
    )

    result = await provider.get("synthetic-job-id")

    assert result.provider == "aws-textract"
    assert result.status == "succeeded"
    assert result.page_count == 1
    assert result.text == "Extracted synthetic line"

    assert client.get_calls == [
        {
            "JobId": "synthetic-job-id",
            "MaxResults": 1000,
        }
    ]


@pytest.mark.asyncio
async def test_real_adapter_preserves_in_progress_status() -> None:
    client = FakeTextractClient(
        get_response={
            "JobStatus": "IN_PROGRESS",
        },
    )

    provider = TextractDocumentIntelligence(
        client=client,
    )

    result = await provider.get("synthetic-job-id")

    assert result.status == "in_progress"
    assert result.text == ""


@pytest.mark.asyncio
async def test_real_adapter_preserves_failed_status() -> None:
    client = FakeTextractClient(
        get_response={
            "JobStatus": "FAILED",
        },
    )

    provider = TextractDocumentIntelligence(
        client=client,
    )

    result = await provider.get("synthetic-job-id")

    assert result.status == "failed"
    assert result.text == ""


@pytest.mark.asyncio
async def test_real_adapter_rejects_blank_get_job_id() -> None:
    client = FakeTextractClient()

    provider = TextractDocumentIntelligence(
        client=client,
    )

    with pytest.raises(
        ValueError,
        match="job_id",
    ):
        await provider.get(" ")

    assert client.get_calls == []


@pytest.mark.asyncio
async def test_real_adapter_health_is_zero_network() -> None:
    client = FakeTextractClient()

    provider = TextractDocumentIntelligence(
        client=client,
    )

    health = await provider.health()

    assert health == {
        "provider": "aws-textract",
        "network_checked": False,
        "max_results": 1000,
        "max_pages": 20,
    }

    assert client.start_calls == []
    assert client.get_calls == []


def test_factory_returns_mock_in_mock_mode_without_boto3() -> None:
    sys.modules.pop("boto3", None)

    settings = _settings(
        mode="mock",
    )

    gateway = build_aws_intelligence_gateway(settings)

    provider = build_aws_document_intelligence_provider(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        provider,
        MockTextractDocumentIntelligence,
    )

    assert "boto3" not in sys.modules


def test_factory_uses_textract_in_document_region_for_sdk_mode() -> None:
    client = FakeTextractClient()

    factory = FakeTextractClientFactory(client)

    settings = _settings(
        mode="sdk",
    )

    gateway = build_aws_intelligence_gateway(
        settings,
        client_factory=factory,
    )

    provider = build_aws_document_intelligence_provider(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        provider,
        TextractDocumentIntelligence,
    )

    assert factory.calls == [
        (
            "textract",
            "eu-west-1",
        )
    ]


def test_factory_rejects_disabled_textract() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
    )

    gateway = AWSIntelligenceGateway(settings)

    with pytest.raises(
        ValueError,
        match="aws_textract_enabled=true",
    ):
        build_aws_document_intelligence_provider(
            settings=settings,
            gateway=gateway,
        )
