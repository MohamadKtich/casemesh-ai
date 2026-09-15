from __future__ import annotations

from datetime import (
    UTC,
    datetime,
    timedelta,
)

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws.clients import (
    Boto3AWSClientFactory,
    MockAWSClientFactory,
)
from casemesh.integrations.aws.federated_credentials import (
    AWSWebIdentityExchangeError,
    AWSWebIdentitySTSExchange,
    AzureContainerAppsManagedIdentityTokenSource,
    AzureFederatedAWSClientFactory,
    AzureFederatedCredentialRefresher,
    AzureManagedIdentityTokenError,
    build_aws_client_factory,
)
from casemesh.integrations.aws.identity import (
    AzureFederatedIdentityConfig,
)

ROLE_ARN = "arn:aws:iam::123456789012:role/CaseMeshRuntime"

AUDIENCE = "api://casemesh-aws"

CLIENT_ID = "11111111-1111-1111-1111-111111111111"


def _config() -> AzureFederatedIdentityConfig:
    return AzureFederatedIdentityConfig(
        role_arn=ROLE_ARN,
        audience=AUDIENCE,
        managed_identity_client_id=(CLIENT_ID),
        role_session_name=("casemesh-api"),
    )


class FakeHTTPResponse:
    def __init__(
        self,
        payload: object,
    ) -> None:
        self._payload = payload

    def raise_for_status(
        self,
    ) -> None:
        return None

    def json(
        self,
    ) -> object:
        return self._payload


class FakeHTTPClient:
    def __init__(
        self,
        payload: object,
    ) -> None:
        self.payload = payload

        self.calls: list[
            dict[
                str,
                object,
            ]
        ] = []

        self.closed = False

    def get(
        self,
        url: str,
        *,
        params: object,
        headers: object,
    ) -> FakeHTTPResponse:
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
            }
        )

        return FakeHTTPResponse(self.payload)

    def close(
        self,
    ) -> None:
        self.closed = True


class FakeSTSClient:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            dict[
                str,
                object,
            ]
        ] = []

    def assume_role_with_web_identity(
        self,
        **kwargs: object,
    ) -> dict[str, object]:
        self.calls.append(dict(kwargs))

        return {
            "Credentials": {
                "AccessKeyId": ("ASIAFAKEACCESSKEY"),
                "SecretAccessKey": ("fake-secret-key"),
                "SessionToken": ("fake-session-token"),
                "Expiration": (datetime.now(UTC) + timedelta(hours=1)),
            }
        }


class FailingSTSClient:
    def assume_role_with_web_identity(
        self,
        **kwargs: object,
    ) -> dict[str, object]:
        token = kwargs.get("WebIdentityToken")

        raise RuntimeError(f"synthetic provider failure containing {token}")


class FakeTokenSource:
    def __init__(
        self,
        token: str,
    ) -> None:
        self.token = token

        self.calls = 0

    def fetch_token(
        self,
    ) -> str:
        self.calls += 1

        return self.token


class FakeSTSExchange:
    def __init__(
        self,
    ) -> None:
        self.tokens: list[str] = []

    def exchange(
        self,
        web_identity_token: str,
    ) -> dict[str, str]:
        self.tokens.append(web_identity_token)

        return {
            "access_key": ("ASIAFAKEACCESSKEY"),
            "secret_key": ("fake-secret-key"),
            "token": ("fake-session-token"),
            "expiry_time": ("2099-01-01T00:00:00Z"),
        }


class FakeBotocoreSession:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            dict[
                str,
                object,
            ]
        ] = []

        self.client = object()

    def create_client(
        self,
        service_name: str,
        *,
        region_name: str,
        config: object,
    ) -> object:
        self.calls.append(
            {
                "service_name": (service_name),
                "region_name": (region_name),
                "config": config,
            }
        )

        return self.client


def test_managed_identity_token_source_uses_container_apps_contract() -> None:
    client = FakeHTTPClient({"access_token": ("fake-entra-token")})

    source = AzureContainerAppsManagedIdentityTokenSource(
        _config(),
        request_timeout_seconds=5,
        environment={
            "IDENTITY_ENDPOINT": ("http://127.0.0.1:42356/msi/token"),
            "IDENTITY_HEADER": ("fake-identity-header"),
        },
        http_client=client,
    )

    token = source.fetch_token()

    assert token == ("fake-entra-token")

    assert len(client.calls) == 1

    call = client.calls[0]

    assert call["url"] == ("http://127.0.0.1:42356/msi/token")

    assert call["params"] == {
        "resource": AUDIENCE,
        "api-version": ("2019-08-01"),
        "client_id": CLIENT_ID,
    }

    assert call["headers"] == {"X-IDENTITY-HEADER": ("fake-identity-header")}


@pytest.mark.parametrize(
    "environment",
    (
        {"IDENTITY_HEADER": ("header")},
        {"IDENTITY_ENDPOINT": ("http://127.0.0.1/token")},
    ),
)
def test_managed_identity_token_source_requires_runtime_contract(
    environment: dict[str, str],
) -> None:
    source = AzureContainerAppsManagedIdentityTokenSource(
        _config(),
        request_timeout_seconds=5,
        environment=environment,
        http_client=(FakeHTTPClient({"access_token": ("never-used")})),
    )

    with pytest.raises(
        AzureManagedIdentityTokenError,
    ):
        source.fetch_token()


def test_managed_identity_token_error_does_not_expose_identity_header() -> None:
    secret_header = "never-log-this-header"

    source = AzureContainerAppsManagedIdentityTokenSource(
        _config(),
        request_timeout_seconds=5,
        environment={
            "IDENTITY_ENDPOINT": ("http://127.0.0.1/token"),
            "IDENTITY_HEADER": (secret_header),
        },
        http_client=(FakeHTTPClient({})),
    )

    with pytest.raises(
        AzureManagedIdentityTokenError,
    ) as exc_info:
        source.fetch_token()

    assert secret_header not in str(exc_info.value)


def test_sts_exchange_returns_botocore_refresh_metadata() -> None:
    client = FakeSTSClient()

    exchange = AWSWebIdentitySTSExchange(
        _config(),
        sts_region_name=("me-central-1"),
        request_timeout_seconds=5,
        sts_client=client,
    )

    metadata = exchange.exchange("fake-entra-token")

    assert set(metadata) == {
        "access_key",
        "secret_key",
        "token",
        "expiry_time",
    }

    assert metadata["access_key"] == ("ASIAFAKEACCESSKEY")

    assert metadata["secret_key"] == ("fake-secret-key")

    assert metadata["token"] == ("fake-session-token")

    assert metadata["expiry_time"].endswith("Z")

    assert len(client.calls) == 1

    call = client.calls[0]

    assert call["RoleArn"] == ROLE_ARN

    assert call["RoleSessionName"] == ("casemesh-api")

    assert call["WebIdentityToken"] == ("fake-entra-token")

    assert call["DurationSeconds"] == 3600


def test_sts_exchange_error_does_not_expose_web_identity_token() -> None:
    secret_token = "never-log-this-token"

    exchange = AWSWebIdentitySTSExchange(
        _config(),
        sts_region_name=("me-central-1"),
        request_timeout_seconds=5,
        sts_client=(FailingSTSClient()),
    )

    with pytest.raises(
        AWSWebIdentityExchangeError,
    ) as exc_info:
        exchange.exchange(secret_token)

    assert secret_token not in str(exc_info.value)


def test_refresher_chains_managed_identity_and_sts_without_persistence() -> None:
    token_source = FakeTokenSource("fake-entra-token")

    sts_exchange = FakeSTSExchange()

    refresher = AzureFederatedCredentialRefresher(
        _config(),
        sts_region_name=("me-central-1"),
        request_timeout_seconds=5,
        token_source=(token_source),
        sts_exchange=(sts_exchange),
    )

    metadata = refresher.refresh()

    assert token_source.calls == 1

    assert sts_exchange.tokens == ["fake-entra-token"]

    assert metadata["access_key"] == ("ASIAFAKEACCESSKEY")


def test_federated_client_factory_caches_clients_and_preserves_transport_limits() -> None:
    session = FakeBotocoreSession()

    factory = AzureFederatedAWSClientFactory(
        _config(),
        sts_region_name=("me-central-1"),
        request_timeout_seconds=7,
        refresh_using=lambda: {
            "access_key": ("ASIAFAKEACCESSKEY"),
            "secret_key": ("fake-secret-key"),
            "token": ("fake-session-token"),
            "expiry_time": ("2099-01-01T00:00:00Z"),
        },
        botocore_session=(session),
    )

    first = factory.create_client(
        service_name=("bedrock-runtime"),
        region_name=("me-central-1"),
    )

    second = factory.create_client(
        service_name=("bedrock-runtime"),
        region_name=("me-central-1"),
    )

    assert first is second

    assert len(session.calls) == 1

    config = session.calls[0]["config"]

    assert config.connect_timeout == 7

    assert config.read_timeout == 7

    retries = config.retries

    assert retries["total_max_attempts"] == 1


def test_factory_selection_preserves_mock_and_default_chain() -> None:
    mock_settings = Settings(
        _env_file=None,
        aws_client_mode="mock",
    )

    mock_factory = build_aws_client_factory(mock_settings)

    assert isinstance(
        mock_factory,
        MockAWSClientFactory,
    )

    sdk_settings = Settings(
        _env_file=None,
        aws_client_mode="sdk",
        aws_identity_mode=("default_chain"),
    )

    sdk_factory = build_aws_client_factory(sdk_settings)

    assert isinstance(
        sdk_factory,
        Boto3AWSClientFactory,
    )


def test_factory_selection_uses_federated_factory_without_network_call() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_identity_mode=("azure_federated"),
        aws_federated_role_arn=(ROLE_ARN),
        aws_federated_audience=(AUDIENCE),
        azure_managed_identity_client_id=(CLIENT_ID),
        aws_federated_role_session_name=("casemesh-api"),
    )

    factory = build_aws_client_factory(settings)

    assert isinstance(
        factory,
        AzureFederatedAWSClientFactory,
    )
