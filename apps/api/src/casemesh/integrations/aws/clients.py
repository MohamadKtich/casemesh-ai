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
    """Lazy boto3 client factory.

    boto3 is intentionally imported only when an AWS service client is
    actually requested. Importing CaseMesh or constructing the AWS gateway
    therefore does not load the AWS SDK or trigger credential resolution.
    """

    def __init__(self) -> None:
        self._clients: dict[tuple[str, str], object] = {}

    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        key = (service_name, region_name)

        if key in self._clients:
            return self._clients[key]

        try:
            boto3 = import_module("boto3")
        except ModuleNotFoundError as exc:
            raise AWSClientDependencyError(
                "AWS capability was requested but boto3 is not installed."
            ) from exc

        client_factory = getattr(boto3, "client", None)

        if not callable(client_factory):
            raise AWSClientDependencyError(
                "The loaded boto3 module does not expose a callable client factory."
            )

        client = cast(
            object,
            client_factory(
                service_name,
                region_name=region_name,
            ),
        )

        self._clients[key] = client
        return client
