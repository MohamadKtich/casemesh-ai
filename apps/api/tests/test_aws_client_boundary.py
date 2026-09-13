from types import SimpleNamespace

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws import (
    AWSClientAccessError,
    AWSIntelligenceGateway,
    Boto3AWSClientFactory,
)


class RecordingClientFactory:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        self.calls.append((service_name, region_name))

        return {
            "service_name": service_name,
            "region_name": region_name,
        }


@pytest.mark.asyncio
async def test_disabled_gateway_never_touches_client_factory() -> None:
    factory = RecordingClientFactory()

    gateway = AWSIntelligenceGateway(
        Settings(_env_file=None),
        client_factory=factory,
    )

    gateway.status()
    await gateway.health()

    assert factory.calls == []


def test_disabled_bedrock_client_is_rejected_before_factory_use() -> None:
    factory = RecordingClientFactory()

    gateway = AWSIntelligenceGateway(
        Settings(_env_file=None),
        client_factory=factory,
    )

    with pytest.raises(
        AWSClientAccessError,
        match="master_disabled",
    ):
        gateway.bedrock_runtime_client()

    assert factory.calls == []


def test_feature_disabled_is_rejected_before_factory_use() -> None:
    factory = RecordingClientFactory()

    gateway = AWSIntelligenceGateway(
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
        ),
        client_factory=factory,
    )

    with pytest.raises(
        AWSClientAccessError,
        match="feature_disabled",
    ):
        gateway.bedrock_runtime_client()

    assert factory.calls == []


def test_bedrock_client_uses_ai_region() -> None:
    factory = RecordingClientFactory()

    gateway = AWSIntelligenceGateway(
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_bedrock_review_enabled=True,
            aws_bedrock_model_id="synthetic-model",
        ),
        client_factory=factory,
    )

    client = gateway.bedrock_runtime_client()

    assert client == {
        "service_name": "bedrock-runtime",
        "region_name": "me-central-1",
    }

    assert factory.calls == [
        ("bedrock-runtime", "me-central-1"),
    ]


def test_document_clients_use_document_region() -> None:
    factory = RecordingClientFactory()

    gateway = AWSIntelligenceGateway(
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_async_processing_enabled=True,
            aws_textract_enabled=True,
            aws_textract_bucket="synthetic-bucket",
            aws_textract_completion_topic_arn="synthetic-topic",
            aws_textract_queue_url="synthetic-queue",
        ),
        client_factory=factory,
    )

    gateway.s3_staging_client()
    gateway.textract_client()
    gateway.sqs_client()

    assert factory.calls == [
        ("s3", "eu-west-1"),
        ("textract", "eu-west-1"),
        ("sqs", "eu-west-1"),
    ]


def test_human_alerts_sns_uses_ai_region() -> None:
    factory = RecordingClientFactory()

    gateway = AWSIntelligenceGateway(
        Settings(
            _env_file=None,
            aws_intelligence_enabled=True,
            aws_sns_alerts_enabled=True,
            aws_human_alert_topic_arn="synthetic-topic",
        ),
        client_factory=factory,
    )

    gateway.human_alerts_sns_client()

    assert factory.calls == [
        ("sns", "me-central-1"),
    ]


def test_boto3_import_is_lazy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import_calls: list[str] = []

    def fake_import(name: str) -> object:
        import_calls.append(name)

        def fake_client(
            service_name: str,
            *,
            region_name: str,
        ) -> object:
            return {
                "service_name": service_name,
                "region_name": region_name,
            }

        return SimpleNamespace(client=fake_client)

    monkeypatch.setattr(
        "casemesh.integrations.aws.clients.import_module",
        fake_import,
    )

    factory = Boto3AWSClientFactory()

    assert import_calls == []

    first = factory.create_client(
        service_name="bedrock-runtime",
        region_name="me-central-1",
    )

    assert import_calls == ["boto3"]

    second = factory.create_client(
        service_name="bedrock-runtime",
        region_name="me-central-1",
    )

    assert first is second
    assert import_calls == ["boto3"]


def test_boto3_dependency_error_is_deferred_until_client_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from casemesh.integrations.aws import (
        AWSClientDependencyError,
    )

    def missing_import(name: str) -> object:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(
        "casemesh.integrations.aws.clients.import_module",
        missing_import,
    )

    factory = Boto3AWSClientFactory()

    with pytest.raises(
        AWSClientDependencyError,
        match="boto3 is not installed",
    ):
        factory.create_client(
            service_name="bedrock-runtime",
            region_name="me-central-1",
        )
