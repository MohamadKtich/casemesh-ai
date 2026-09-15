"""Azure workload federation for AWS service clients.

The implementation exchanges a Microsoft Entra managed-identity token for
short-lived AWS credentials via STS AssumeRoleWithWebIdentity.

Credential values are memory-only. They are never persisted or logged.
Real cloud calls occur only when this provider is used at runtime.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from importlib import import_module
from typing import Protocol, cast
from urllib.parse import urlparse

from casemesh.core.config import Settings
from casemesh.integrations.aws.clients import (
    AWSClientFactory,
    Boto3AWSClientFactory,
    MockAWSClientFactory,
)
from casemesh.integrations.aws.identity import (
    AzureFederatedIdentityConfig,
    build_aws_identity_config,
)

DEFAULT_FEDERATED_SESSION_SECONDS = 3600


CredentialMetadata = dict[str, str]


class AWSFederatedIdentityError(RuntimeError):
    """Base error for Azure-to-AWS workload federation."""


class AzureManagedIdentityTokenError(
    AWSFederatedIdentityError,
):
    """Managed-identity token acquisition failed."""


class AWSWebIdentityExchangeError(
    AWSFederatedIdentityError,
):
    """AWS STS web-identity exchange failed."""


class AWSFederatedIdentityDependencyError(
    AWSFederatedIdentityError,
):
    """A required runtime dependency is unavailable."""


class _ManagedIdentityHTTPResponse(Protocol):
    def raise_for_status(
        self,
    ) -> None: ...

    def json(
        self,
    ) -> object: ...


class _ManagedIdentityHTTPClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> _ManagedIdentityHTTPResponse: ...

    def close(
        self,
    ) -> None: ...


class _STSClient(Protocol):
    def assume_role_with_web_identity(
        self,
        *,
        RoleArn: str,
        RoleSessionName: str,
        WebIdentityToken: str,
        DurationSeconds: int,
    ) -> dict[str, object]: ...


class _BotocoreSession(Protocol):
    def create_client(
        self,
        service_name: str,
        *,
        region_name: str,
        config: object,
    ) -> object: ...


class AzureContainerAppsManagedIdentityTokenSource:
    """Acquire an Entra token from the Container Apps identity endpoint."""

    def __init__(
        self,
        config: AzureFederatedIdentityConfig,
        *,
        request_timeout_seconds: float,
        environment: Mapping[str, str] | None = None,
        http_client: _ManagedIdentityHTTPClient | None = None,
    ) -> None:
        if request_timeout_seconds <= 0:
            raise ValueError("Managed identity request timeout must be greater than zero.")

        self._config = config
        self._request_timeout_seconds = request_timeout_seconds

        self._environment = os.environ if environment is None else environment

        self._http_client = http_client

    def fetch_token(
        self,
    ) -> str:
        endpoint = self._environment.get(
            "IDENTITY_ENDPOINT",
            "",
        ).strip()

        identity_header = self._environment.get(
            "IDENTITY_HEADER",
            "",
        ).strip()

        if not endpoint:
            raise AzureManagedIdentityTokenError(
                "Azure Container Apps IDENTITY_ENDPOINT is unavailable."
            )

        if not identity_header:
            raise AzureManagedIdentityTokenError(
                "Azure Container Apps IDENTITY_HEADER is unavailable."
            )

        parsed = urlparse(endpoint)

        if (
            parsed.scheme
            not in {
                "http",
                "https",
            }
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise AzureManagedIdentityTokenError("Azure managed identity endpoint is invalid.")

        client = self._http_client
        close_client = False

        if client is None:
            client = self._build_http_client()

            close_client = True

        try:
            response = client.get(
                endpoint,
                params={
                    "resource": (self._config.audience),
                    "api-version": ("2019-08-01"),
                    "client_id": (self._config.managed_identity_client_id),
                },
                headers={
                    "X-IDENTITY-HEADER": (identity_header),
                },
            )

            response.raise_for_status()

            payload = response.json()

        except Exception:
            raise AzureManagedIdentityTokenError(
                "Azure managed identity token acquisition failed."
            ) from None

        finally:
            if close_client:
                with suppress(Exception):
                    client.close()

        if not isinstance(
            payload,
            Mapping,
        ):
            raise AzureManagedIdentityTokenError(
                "Azure managed identity returned an invalid token payload."
            )

        payload_map = cast(
            Mapping[str, object],
            payload,
        )

        token = payload_map.get("access_token")

        if (
            not isinstance(
                token,
                str,
            )
            or not token.strip()
        ):
            raise AzureManagedIdentityTokenError(
                "Azure managed identity response did not contain an access token."
            )

        return token.strip()

    def _build_http_client(
        self,
    ) -> _ManagedIdentityHTTPClient:
        try:
            httpx = import_module("httpx")

        except ModuleNotFoundError:
            raise AWSFederatedIdentityDependencyError("Azure federation requires httpx.") from None

        client_factory = getattr(
            httpx,
            "Client",
            None,
        )

        if not callable(client_factory):
            raise AWSFederatedIdentityDependencyError(
                "The loaded httpx module does not expose Client."
            )

        client = client_factory(
            timeout=(self._request_timeout_seconds),
            trust_env=False,
            follow_redirects=False,
        )

        return cast(
            _ManagedIdentityHTTPClient,
            client,
        )


class AWSWebIdentitySTSExchange:
    """Exchange an Entra token for temporary AWS credentials."""

    def __init__(
        self,
        config: AzureFederatedIdentityConfig,
        *,
        sts_region_name: str,
        request_timeout_seconds: float,
        sts_client: _STSClient | None = None,
    ) -> None:
        if request_timeout_seconds <= 0:
            raise ValueError("AWS STS request timeout must be greater than zero.")

        if not sts_region_name.strip():
            raise ValueError("AWS STS region must not be empty.")

        self._config = config

        self._sts_region_name = sts_region_name.strip()

        self._request_timeout_seconds = request_timeout_seconds

        self._sts_client = sts_client

    def exchange(
        self,
        web_identity_token: str,
    ) -> CredentialMetadata:
        if not web_identity_token.strip():
            raise AWSWebIdentityExchangeError("AWS STS web identity token must not be empty.")

        try:
            response = self._client().assume_role_with_web_identity(
                RoleArn=(self._config.role_arn),
                RoleSessionName=(self._config.role_session_name),
                WebIdentityToken=(web_identity_token),
                DurationSeconds=(DEFAULT_FEDERATED_SESSION_SECONDS),
            )

        except Exception:
            raise AWSWebIdentityExchangeError("AWS STS web identity exchange failed.") from None

        credentials = response.get("Credentials")

        if not isinstance(
            credentials,
            Mapping,
        ):
            raise AWSWebIdentityExchangeError("AWS STS response did not contain credentials.")

        credential_map = cast(
            Mapping[str, object],
            credentials,
        )

        access_key = credential_map.get("AccessKeyId")

        secret_key = credential_map.get("SecretAccessKey")

        session_token = credential_map.get("SessionToken")

        expiration = credential_map.get("Expiration")

        if (
            not isinstance(
                access_key,
                str,
            )
            or not access_key
            or not isinstance(
                secret_key,
                str,
            )
            or not secret_key
            or not isinstance(
                session_token,
                str,
            )
            or not session_token
        ):
            raise AWSWebIdentityExchangeError("AWS STS returned incomplete temporary credentials.")

        expiry_time = self._normalize_expiration(expiration)

        return {
            "access_key": access_key,
            "secret_key": secret_key,
            "token": session_token,
            "expiry_time": expiry_time,
        }

    def _client(
        self,
    ) -> _STSClient:
        existing = self._sts_client

        if existing is not None:
            return existing

        try:
            botocore = import_module("botocore")

            botocore_config = import_module("botocore.config")

            botocore_session = import_module("botocore.session")

        except ModuleNotFoundError:
            raise AWSFederatedIdentityDependencyError(
                "Azure federation requires botocore."
            ) from None

        unsigned = getattr(
            botocore,
            "UNSIGNED",
            None,
        )

        config_factory = getattr(
            botocore_config,
            "Config",
            None,
        )

        session_factory = getattr(
            botocore_session,
            "Session",
            None,
        )

        if unsigned is None or not callable(config_factory) or not callable(session_factory):
            raise AWSFederatedIdentityDependencyError("The loaded botocore package is incomplete.")

        transport_config = config_factory(
            signature_version=(unsigned),
            connect_timeout=(self._request_timeout_seconds),
            read_timeout=(self._request_timeout_seconds),
            retries={
                "mode": "standard",
                "total_max_attempts": 1,
            },
        )

        session = session_factory()

        create_client = getattr(
            session,
            "create_client",
            None,
        )

        if not callable(create_client):
            raise AWSFederatedIdentityDependencyError(
                "The loaded botocore Session cannot create clients."
            )

        client = create_client(
            "sts",
            region_name=(self._sts_region_name),
            config=(transport_config),
        )

        self._sts_client = cast(
            _STSClient,
            client,
        )

        return self._sts_client

    @staticmethod
    def _normalize_expiration(
        value: object,
    ) -> str:
        parsed: datetime

        if isinstance(
            value,
            datetime,
        ):
            parsed = value

        elif isinstance(
            value,
            str,
        ):
            try:
                parsed = datetime.fromisoformat(
                    value.replace(
                        "Z",
                        "+00:00",
                    )
                )

            except ValueError:
                raise AWSWebIdentityExchangeError(
                    "AWS STS returned an invalid credential expiration."
                ) from None

        else:
            raise AWSWebIdentityExchangeError("AWS STS credential expiration is missing.")

        if parsed.tzinfo is None:
            raise AWSWebIdentityExchangeError(
                "AWS STS credential expiration must include a timezone."
            )

        normalized = parsed.astimezone(UTC)

        if normalized <= datetime.now(UTC):
            raise AWSWebIdentityExchangeError("AWS STS returned expired temporary credentials.")

        return normalized.isoformat().replace(
            "+00:00",
            "Z",
        )


class AzureFederatedCredentialRefresher:
    """Refresh callback consumed by botocore credentials."""

    def __init__(
        self,
        config: AzureFederatedIdentityConfig,
        *,
        sts_region_name: str,
        request_timeout_seconds: float,
        token_source: (AzureContainerAppsManagedIdentityTokenSource | None) = None,
        sts_exchange: (AWSWebIdentitySTSExchange | None) = None,
    ) -> None:
        self._token_source = token_source or AzureContainerAppsManagedIdentityTokenSource(
            config,
            request_timeout_seconds=(request_timeout_seconds),
        )

        self._sts_exchange = sts_exchange or AWSWebIdentitySTSExchange(
            config,
            sts_region_name=(sts_region_name),
            request_timeout_seconds=(request_timeout_seconds),
        )

    def refresh(
        self,
    ) -> CredentialMetadata:
        web_identity_token = self._token_source.fetch_token()

        return self._sts_exchange.exchange(web_identity_token)


class AzureFederatedAWSClientFactory:
    """AWS service client factory backed by refreshable web identity."""

    def __init__(
        self,
        config: AzureFederatedIdentityConfig,
        *,
        sts_region_name: str,
        request_timeout_seconds: float = 30.0,
        refresh_using: (
            Callable[
                [],
                CredentialMetadata,
            ]
            | None
        ) = None,
        botocore_session: (_BotocoreSession | None) = None,
    ) -> None:
        if request_timeout_seconds <= 0:
            raise ValueError("AWS SDK request_timeout_seconds must be greater than zero.")

        self._config = config

        self._sts_region_name = sts_region_name

        self._request_timeout_seconds = request_timeout_seconds

        if refresh_using is None:
            refresher = AzureFederatedCredentialRefresher(
                config,
                sts_region_name=(sts_region_name),
                request_timeout_seconds=(request_timeout_seconds),
            )

            refresh_using = refresher.refresh

        self._refresh_using = refresh_using

        self._botocore_session = botocore_session

        self._clients: dict[
            tuple[
                str,
                str,
            ],
            object,
        ] = {}

        self._transport_config: object | None = None

    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        key = (
            service_name,
            region_name,
        )

        existing = self._clients.get(key)

        if existing is not None:
            return existing

        session = self._session()

        client = session.create_client(
            service_name,
            region_name=(region_name),
            config=(self._sdk_transport_config()),
        )

        self._clients[key] = client

        return client

    def _session(
        self,
    ) -> _BotocoreSession:
        existing = self._botocore_session

        if existing is not None:
            return existing

        try:
            credentials_module = import_module("botocore.credentials")

            session_module = import_module("botocore.session")

        except ModuleNotFoundError:
            raise AWSFederatedIdentityDependencyError(
                "Azure federation requires botocore."
            ) from None

        credentials_factory = getattr(
            credentials_module,
            "DeferredRefreshableCredentials",
            None,
        )

        session_factory = getattr(
            session_module,
            "Session",
            None,
        )

        if not callable(credentials_factory) or not callable(session_factory):
            raise AWSFederatedIdentityDependencyError(
                "The loaded botocore package does not support refreshable credentials."
            )

        credentials = credentials_factory(
            refresh_using=(self._refresh_using),
            method=("azure-container-apps-web-identity"),
        )

        session = session_factory()

        session._credentials = credentials

        self._botocore_session = cast(
            _BotocoreSession,
            session,
        )

        return self._botocore_session

    def _sdk_transport_config(
        self,
    ) -> object:
        existing = self._transport_config

        if existing is not None:
            return existing

        try:
            botocore_config = import_module("botocore.config")

        except ModuleNotFoundError:
            raise AWSFederatedIdentityDependencyError(
                "Azure federation requires botocore."
            ) from None

        config_factory = getattr(
            botocore_config,
            "Config",
            None,
        )

        if not callable(config_factory):
            raise AWSFederatedIdentityDependencyError(
                "The loaded botocore package does not expose Config."
            )

        config = config_factory(
            connect_timeout=(self._request_timeout_seconds),
            read_timeout=(self._request_timeout_seconds),
            retries={
                "mode": "standard",
                "total_max_attempts": 1,
            },
        )

        self._transport_config = config

        return config


def build_aws_client_factory(
    settings: Settings,
) -> AWSClientFactory:
    """Select the configured AWS credential/client strategy."""

    if settings.aws_client_mode == "mock":
        return MockAWSClientFactory()

    if settings.aws_identity_mode == "default_chain":
        return Boto3AWSClientFactory(request_timeout_seconds=(settings.aws_request_timeout_seconds))

    config = build_aws_identity_config(settings)

    if config is None:
        raise ValueError("Azure federated AWS identity configuration is unavailable.")

    return AzureFederatedAWSClientFactory(
        config,
        sts_region_name=(settings.aws_ai_region),
        request_timeout_seconds=(settings.aws_request_timeout_seconds),
    )
