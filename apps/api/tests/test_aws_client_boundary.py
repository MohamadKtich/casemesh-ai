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
    monkeypatch,
) -> None:
    import casemesh.integrations.aws.clients as clients_module

    imports: list[str] = []
    created_clients: list[dict[str, object]] = []

    class FakeConfig:
        def __init__(
            self,
            **kwargs: object,
        ) -> None:
            self.kwargs = kwargs

    class FakeBoto3:
        @staticmethod
        def client(
            service_name: str,
            **kwargs: object,
        ) -> object:
            record = {
                "service_name": service_name,
                **kwargs,
            }

            created_clients.append(record)

            return object()

    class FakeBotocoreConfigModule:
        Config = FakeConfig

    def fake_import_module(
        name: str,
    ) -> object:
        imports.append(name)

        if name == "boto3":
            return FakeBoto3()

        if name == "botocore.config":
            return FakeBotocoreConfigModule()

        raise AssertionError(f"Unexpected module import: {name}")

    monkeypatch.setattr(
        clients_module,
        "import_module",
        fake_import_module,
    )

    factory = clients_module.Boto3AWSClientFactory(
        request_timeout_seconds=7.5,
    )

    assert imports == []

    first = factory.create_client(
        service_name="sns",
        region_name="me-central-1",
    )

    second = factory.create_client(
        service_name="sns",
        region_name="me-central-1",
    )

    assert first is second

    assert imports == [
        "boto3",
        "botocore.config",
    ]

    assert len(created_clients) == 1

    created = created_clients[0]

    assert created["service_name"] == "sns"

    assert created["region_name"] == "me-central-1"

    config = created["config"]

    assert isinstance(
        config,
        FakeConfig,
    )

    assert config.kwargs == {
        "connect_timeout": 7.5,
        "read_timeout": 7.5,
        "retries": {
            "mode": "standard",
            "total_max_attempts": 1,
        },
    }


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


def test_boto3_factory_rejects_non_positive_transport_timeout() -> None:
    import pytest

    from casemesh.integrations.aws.clients import (
        Boto3AWSClientFactory,
    )

    with pytest.raises(
        ValueError,
        match="request_timeout_seconds",
    ):
        Boto3AWSClientFactory(
            request_timeout_seconds=0,
        )


def test_sdk_gateway_factory_propagates_configured_timeout(
    monkeypatch,
) -> None:
    import casemesh.integrations.aws.factory as factory_module
    from casemesh.core.config import Settings

    observed: list[float] = []

    class RecordingFactory:
        def __init__(
            self,
            *,
            request_timeout_seconds: float,
        ) -> None:
            observed.append(request_timeout_seconds)

        def create_client(
            self,
            *,
            service_name: str,
            region_name: str,
        ) -> object:
            del service_name
            del region_name

            raise AssertionError("No AWS client should be requested during gateway construction.")

    monkeypatch.setattr(
        factory_module,
        "Boto3AWSClientFactory",
        RecordingFactory,
    )

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_request_timeout_seconds=9.25,
    )

    gateway = factory_module.build_aws_intelligence_gateway(settings)

    assert gateway is not None

    assert observed == [
        9.25,
    ]


def test_direct_gateway_fallback_propagates_configured_timeout(
    monkeypatch,
) -> None:
    import casemesh.integrations.aws.gateway as gateway_module
    from casemesh.core.config import Settings

    observed: list[float] = []

    class RecordingFactory:
        def __init__(
            self,
            *,
            request_timeout_seconds: float,
        ) -> None:
            observed.append(request_timeout_seconds)

        def create_client(
            self,
            *,
            service_name: str,
            region_name: str,
        ) -> object:
            del service_name
            del region_name

            return object()

    monkeypatch.setattr(
        gateway_module,
        "Boto3AWSClientFactory",
        RecordingFactory,
    )

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_request_timeout_seconds=6.5,
    )

    gateway = gateway_module.AWSIntelligenceGateway(settings)

    factory = gateway._clients()

    assert isinstance(
        factory,
        RecordingFactory,
    )

    assert observed == [
        6.5,
    ]
