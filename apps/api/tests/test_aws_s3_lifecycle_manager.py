import sys

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws import (
    AWSIntelligenceGateway,
    build_aws_intelligence_gateway,
)
from casemesh.integrations.aws.lifecycle import (
    MockS3TemporaryEvidenceLifecycleManager,
    S3TemporaryEvidenceLifecycleManager,
    build_aws_s3_lifecycle_manager,
)


class FakeLifecycleS3Client:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def put_bucket_lifecycle_configuration(
        self,
        **kwargs: object,
    ) -> object:
        self.calls.append(dict(kwargs))
        return {}


class FakeLifecycleClientFactory:
    def __init__(
        self,
        client: FakeLifecycleS3Client,
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
        aws_textract_queue_url="synthetic-queue",
    )


@pytest.mark.asyncio
async def test_real_lifecycle_manager_applies_exact_policy() -> None:
    client = FakeLifecycleS3Client()

    manager = S3TemporaryEvidenceLifecycleManager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    configuration = await manager.apply()

    assert len(client.calls) == 1

    call = client.calls[0]

    assert call["Bucket"] == "synthetic-textract-bucket"
    assert call["LifecycleConfiguration"] == configuration

    rule = configuration["Rules"][0]

    assert rule["Status"] == "Enabled"
    assert rule["Filter"]["Prefix"] == "casemesh-temp/"
    assert rule["Expiration"]["Days"] == 1
    assert rule["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] == 1


@pytest.mark.asyncio
async def test_real_lifecycle_health_does_not_call_aws() -> None:
    client = FakeLifecycleS3Client()

    manager = S3TemporaryEvidenceLifecycleManager(
        client=client,
        bucket="synthetic-textract-bucket",
    )

    health = await manager.health()

    assert health == {
        "provider": "aws-s3-lifecycle",
        "bucket": "synthetic-textract-bucket",
        "network_checked": False,
        "prefix": "casemesh-temp/",
        "expiration_days": 1,
    }

    assert client.calls == []


@pytest.mark.asyncio
async def test_mock_lifecycle_manager_is_zero_network() -> None:
    sys.modules.pop("boto3", None)

    manager = MockS3TemporaryEvidenceLifecycleManager(
        bucket="synthetic-textract-bucket",
    )

    before = await manager.health()

    assert before["applied"] is False

    configuration = await manager.apply()

    after = await manager.health()

    assert after["applied"] is True
    assert configuration["Rules"][0]["Expiration"]["Days"] == 1
    assert "boto3" not in sys.modules


def test_lifecycle_factory_uses_mock_without_boto3() -> None:
    sys.modules.pop("boto3", None)

    settings = _settings(
        mode="mock",
    )

    gateway = build_aws_intelligence_gateway(settings)

    manager = build_aws_s3_lifecycle_manager(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        manager,
        MockS3TemporaryEvidenceLifecycleManager,
    )

    assert "boto3" not in sys.modules


def test_lifecycle_factory_uses_document_region_in_sdk_mode() -> None:
    client = FakeLifecycleS3Client()
    client_factory = FakeLifecycleClientFactory(client)

    settings = _settings(
        mode="sdk",
    )

    gateway = build_aws_intelligence_gateway(
        settings,
        client_factory=client_factory,
    )

    manager = build_aws_s3_lifecycle_manager(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        manager,
        S3TemporaryEvidenceLifecycleManager,
    )

    assert client_factory.calls == [
        (
            "s3",
            "eu-west-1",
        )
    ]


def test_lifecycle_factory_rejects_disabled_textract() -> None:
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
        build_aws_s3_lifecycle_manager(
            settings=settings,
            gateway=gateway,
        )
