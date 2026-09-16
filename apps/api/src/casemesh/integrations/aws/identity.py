"""Non-secret AWS workload identity contracts.

This module performs configuration validation only. It does not acquire
Microsoft Entra tokens, call AWS STS, or create AWS service clients.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from casemesh.core.config import Settings

AWSIdentityMode = Literal[
    "default_chain",
    "azure_federated",
]


_ROLE_ARN_PATTERN = re.compile(
    r"^arn:"
    r"(?:aws|aws-us-gov|aws-cn):"
    r"iam::"
    r"[0-9]{12}:"
    r"role/"
    r"[A-Za-z0-9+=,.@_/-]+$"
)

_ROLE_SESSION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_=,.@-]{2,64}$")


@dataclass(
    frozen=True,
    slots=True,
)
class AzureFederatedIdentityConfig:
    """Validated, non-secret Azure-to-AWS federation configuration."""

    role_arn: str
    audience: str
    managed_identity_client_id: str
    role_session_name: str

    def __post_init__(
        self,
    ) -> None:
        role_arn = self.role_arn.strip()

        audience = self.audience.strip()

        managed_identity_client_id = self.managed_identity_client_id.strip()

        role_session_name = self.role_session_name.strip()

        if not _ROLE_ARN_PATTERN.fullmatch(role_arn):
            raise ValueError("AWS federated role ARN must be a valid IAM role ARN.")

        if not audience or any(character.isspace() for character in audience):
            raise ValueError("AWS federated audience must be non-empty and contain no whitespace.")

        if len(audience) > 255:
            raise ValueError("AWS federated audience must not exceed 255 characters.")

        try:
            parsed_client_id = UUID(managed_identity_client_id)
        except ValueError as exc:
            raise ValueError("Azure managed identity client ID must be a UUID.") from exc

        if str(parsed_client_id) != managed_identity_client_id.lower():
            raise ValueError("Azure managed identity client ID must use canonical UUID form.")

        if not _ROLE_SESSION_NAME_PATTERN.fullmatch(role_session_name):
            raise ValueError(
                "AWS federated role session name must be 2-64 "
                "characters using AWS STS-safe characters."
            )

        object.__setattr__(
            self,
            "role_arn",
            role_arn,
        )

        object.__setattr__(
            self,
            "audience",
            audience,
        )

        object.__setattr__(
            self,
            "managed_identity_client_id",
            managed_identity_client_id.lower(),
        )

        object.__setattr__(
            self,
            "role_session_name",
            role_session_name,
        )


def build_aws_identity_config(
    settings: Settings,
) -> AzureFederatedIdentityConfig | None:
    """Project Settings into a zero-network AWS identity contract.

    default_chain returns None because boto3 owns credential resolution.
    azure_federated returns only the non-secret inputs required by the
    future managed-identity-to-STS exchange.
    """

    if settings.aws_identity_mode == "default_chain":
        return None

    if settings.aws_identity_mode != "azure_federated":
        raise ValueError("Unsupported AWS identity mode.")

    return AzureFederatedIdentityConfig(
        role_arn=(settings.aws_federated_role_arn),
        audience=(settings.aws_federated_audience),
        managed_identity_client_id=(settings.azure_managed_identity_client_id),
        role_session_name=(settings.aws_federated_role_session_name),
    )
