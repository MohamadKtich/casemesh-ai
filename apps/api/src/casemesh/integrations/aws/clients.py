from dataclasses import dataclass
from importlib import import_module
from typing import Literal, Protocol, cast

AWSClientMode = Literal["mock", "sdk"]


class AWSClientDependencyError(RuntimeError):
    """Raised when the AWS SDK cannot be loaded on demand."""


class AWSClientFactory(Protocol):
    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        """Create or return an AWS service client."""


@dataclass(frozen=True, slots=True)
class MockAWSClient:
    """Deterministic offline representation of an AWS service client."""

    service_name: str
    region_name: str
    mode: Literal["mock"] = "mock"


class MockAWSClientFactory:
    """Create deterministic AWS client stand-ins without network access."""

    def __init__(self) -> None:
        self._clients: dict[tuple[str, str], MockAWSClient] = {}

    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        key = (service_name, region_name)

        if key not in self._clients:
            self._clients[key] = MockAWSClient(
                service_name=service_name,
                region_name=region_name,
            )

        return self._clients[key]


class Boto3AWSClientFactory:
    """Lazy boto3 client factory with bounded SDK transport behavior.

    boto3 and botocore are imported only when an AWS client is actually
    requested. SDK clients use bounded connect/read socket timeouts and one
    total SDK attempt so hidden retries cannot duplicate side effects or cost.
    """

    def __init__(
        self,
        *,
        request_timeout_seconds: float = 30.0,
    ) -> None:
        if request_timeout_seconds <= 0:
            raise ValueError("AWS SDK request_timeout_seconds must be greater than zero.")

        self._request_timeout_seconds = request_timeout_seconds

        self._clients: dict[
            tuple[str, str],
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

        if key in self._clients:
            return self._clients[key]

        try:
            boto3 = import_module("boto3")
        except ModuleNotFoundError as exc:
            raise AWSClientDependencyError(
                "AWS capability was requested but boto3 is not installed."
            ) from exc

        client_factory = getattr(
            boto3,
            "client",
            None,
        )

        if not callable(client_factory):
            raise AWSClientDependencyError(
                "The loaded boto3 module does not expose a callable client factory."
            )

        client = cast(
            object,
            client_factory(
                service_name,
                region_name=region_name,
                config=self._sdk_transport_config(),
            ),
        )

        self._clients[key] = client

        return client

    def _sdk_transport_config(
        self,
    ) -> object:
        existing = self._transport_config

        if existing is not None:
            return existing

        try:
            botocore_config = import_module("botocore.config")
        except ModuleNotFoundError as exc:
            raise AWSClientDependencyError(
                "AWS capability was requested but botocore is not installed."
            ) from exc

        config_factory = getattr(
            botocore_config,
            "Config",
            None,
        )

        if not callable(config_factory):
            raise AWSClientDependencyError(
                "The loaded botocore.config module does not expose Config."
            )

        config = cast(
            object,
            config_factory(
                connect_timeout=(self._request_timeout_seconds),
                read_timeout=(self._request_timeout_seconds),
                retries={
                    "mode": "standard",
                    "total_max_attempts": 1,
                },
            ),
        )

        self._transport_config = config

        return config
