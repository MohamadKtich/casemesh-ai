import hashlib
import sys
from uuid import UUID

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws import (
    AWSIntelligenceGateway,
    MockAWSClientFactory,
    build_aws_intelligence_gateway,
)
from casemesh.integrations.aws.staging import (
    MockS3TemporaryEvidenceStager,
    S3TemporaryEvidenceStager,
    build_aws_temporary_evidence_stager,
)
from casemesh.intelligence.staging import (
    StagedEvidenceObject,
    TemporaryEvidenceRequest,
)


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []

    def put_object(
        self,
        **kwargs: object,
    ) -> object:
        self.put_calls.append(dict(kwargs))
        return {"ETag": '"synthetic"'}

    def delete_object(
        self,
        **kwargs: object,
    ) -> object:
        self.delete_calls.append(dict(kwargs))
        return {}


class FakeS3ClientFactory:
    def __init__(
        self,
        client: FakeS3Client,
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


def _request() -> TemporaryEvidenceRequest:
    return TemporaryEvidenceRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        document_id=UUID("33333333-3333-3333-3333-333333333333"),
        content=b"synthetic s3 adapter evidence",
        content_type="application/pdf",
    )


def _sdk_settings() -> Settings:
    return Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket="synthetic-textract-bucket",
        aws_textract_completion_topic_arn="synthetic-topic",
        aws_textract_queue_url="synthetic-queue",
    )


def _mock_settings() -> Settings:
    return Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket="synthetic-textract-bucket",
        aws_textract_completion_topic_arn="synthetic-topic",
        aws_textract_queue_url="synthetic-queue",
    )


@pytest.mark.asyncio
async def test_real_adapter_puts_encrypted_temporary_object() -> None:
    client = FakeS3Client()

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    request = _request()
    digest = hashlib.sha256(request.content).hexdigest()

    staged = await stager.stage(request)

    assert staged.provider == "aws-s3"
    assert staged.bucket == "synthetic-textract-bucket"
    assert staged.sha256 == digest
    assert staged.temporary is True

    assert len(client.put_calls) == 1

    put_call = client.put_calls[0]

    assert put_call["Bucket"] == "synthetic-textract-bucket"
    assert put_call["Key"] == staged.object_key
    assert put_call["Body"] == request.content
    assert put_call["ContentType"] == "application/pdf"
    assert put_call["ServerSideEncryption"] == "AES256"

    assert put_call["Metadata"] == {
        "casemesh-temporary": "true",
        "sha256": digest,
    }


@pytest.mark.asyncio
async def test_real_adapter_metadata_is_deliberately_minimal() -> None:
    client = FakeS3Client()

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    await stager.stage(_request())

    metadata = client.put_calls[0]["Metadata"]

    assert isinstance(metadata, dict)
    assert set(metadata) == {
        "casemesh-temporary",
        "sha256",
    }

    serialized = repr(metadata)

    assert "11111111-1111-1111-1111-111111111111" not in serialized
    assert "22222222-2222-2222-2222-222222222222" not in serialized
    assert "33333333-3333-3333-3333-333333333333" not in serialized


@pytest.mark.asyncio
async def test_real_adapter_deletes_only_owned_object() -> None:
    client = FakeS3Client()

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    staged = await stager.stage(_request())

    await stager.delete(staged)

    assert client.delete_calls == [
        {
            "Bucket": "synthetic-textract-bucket",
            "Key": staged.object_key,
        }
    ]


@pytest.mark.asyncio
async def test_delete_rejects_different_provider_before_client_call() -> None:
    client = FakeS3Client()

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    foreign = StagedEvidenceObject(
        provider="other-provider",
        bucket="synthetic-textract-bucket",
        object_key="casemesh-temp/example",
        sha256="0" * 64,
        size_bytes=1,
        content_type="application/pdf",
    )

    with pytest.raises(
        ValueError,
        match="different provider",
    ):
        await stager.delete(foreign)

    assert client.delete_calls == []


@pytest.mark.asyncio
async def test_delete_rejects_different_bucket_before_client_call() -> None:
    client = FakeS3Client()

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    foreign = StagedEvidenceObject(
        provider="aws-s3",
        bucket="other-bucket",
        object_key="casemesh-temp/example",
        sha256="0" * 64,
        size_bytes=1,
        content_type="application/pdf",
    )

    with pytest.raises(
        ValueError,
        match="different bucket",
    ):
        await stager.delete(foreign)

    assert client.delete_calls == []


@pytest.mark.asyncio
async def test_delete_rejects_key_outside_managed_prefix() -> None:
    client = FakeS3Client()

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    foreign = StagedEvidenceObject(
        provider="aws-s3",
        bucket="synthetic-textract-bucket",
        object_key="unmanaged/example",
        sha256="0" * 64,
        size_bytes=1,
        content_type="application/pdf",
    )

    with pytest.raises(
        ValueError,
        match="managed prefix",
    ):
        await stager.delete(foreign)

    assert client.delete_calls == []


@pytest.mark.asyncio
async def test_real_adapter_health_does_not_call_aws() -> None:
    client = FakeS3Client()

    stager = S3TemporaryEvidenceStager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    health = await stager.health()

    assert health == {
        "provider": "aws-s3",
        "bucket": "synthetic-textract-bucket",
        "network_checked": False,
        "temporary": True,
        "server_side_encryption": "AES256",
    }

    assert client.put_calls == []
    assert client.delete_calls == []


def test_staging_factory_uses_mock_without_importing_boto3() -> None:
    sys.modules.pop("boto3", None)

    settings = _mock_settings()

    gateway = build_aws_intelligence_gateway(
        settings,
        client_factory=MockAWSClientFactory(),
    )

    stager = build_aws_temporary_evidence_stager(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        stager,
        MockS3TemporaryEvidenceStager,
    )

    assert "boto3" not in sys.modules


def test_staging_factory_uses_s3_client_in_sdk_mode() -> None:
    client = FakeS3Client()
    client_factory = FakeS3ClientFactory(client)

    settings = _sdk_settings()

    gateway = build_aws_intelligence_gateway(
        settings,
        client_factory=client_factory,
    )

    stager = build_aws_temporary_evidence_stager(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        stager,
        S3TemporaryEvidenceStager,
    )

    assert client_factory.calls == [
        (
            "s3",
            "eu-west-1",
        )
    ]


def test_staging_factory_rejects_disabled_textract() -> None:
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
        build_aws_temporary_evidence_stager(
            settings=settings,
            gateway=gateway,
        )
