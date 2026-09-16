import sys
from dataclasses import fields

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws.identity import (
    AzureFederatedIdentityConfig,
    build_aws_identity_config,
)

ROLE_ARN = "arn:aws:iam::123456789012:role/CaseMeshRuntime"

AUDIENCE = "api://casemesh-aws"

CLIENT_ID = "11111111-1111-1111-1111-111111111111"


def test_default_chain_has_no_explicit_federation_contract() -> None:
    settings = Settings(
        _env_file=None,
    )

    assert build_aws_identity_config(settings) is None


def test_azure_federated_contract_is_non_secret_and_normalized() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_identity_mode=("azure_federated"),
        aws_federated_role_arn=(f"  {ROLE_ARN}  "),
        aws_federated_audience=(f"  {AUDIENCE}  "),
        azure_managed_identity_client_id=(CLIENT_ID.upper()),
        aws_federated_role_session_name=("  casemesh-api  "),
    )

    config = build_aws_identity_config(settings)

    assert config is not None

    assert config.role_arn == (ROLE_ARN)

    assert config.audience == (AUDIENCE)

    assert config.managed_identity_client_id == CLIENT_ID

    assert config.role_session_name == ("casemesh-api")


def test_identity_contract_contains_no_credential_fields() -> None:
    field_names = {field.name.lower() for field in fields(AzureFederatedIdentityConfig)}

    forbidden_terms = (
        "access_key",
        "secret",
        "session_token",
        "credential",
        "web_identity_token",
    )

    for field_name in field_names:
        assert not any(term in field_name for term in forbidden_terms)


@pytest.mark.parametrize(
    "role_arn",
    (
        "",
        "not-an-arn",
        "arn:aws:s3:::bucket",
        "arn:aws:iam::123:role/short-account",
        "arn:aws:iam::123456789012:user/not-a-role",
    ),
)
def test_federated_contract_rejects_invalid_role_arn(
    role_arn: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="role ARN",
    ):
        AzureFederatedIdentityConfig(
            role_arn=role_arn,
            audience=AUDIENCE,
            managed_identity_client_id=(CLIENT_ID),
            role_session_name=("casemesh-api"),
        )


@pytest.mark.parametrize(
    "audience",
    (
        "",
        " ",
        "api://contains whitespace",
    ),
)
def test_federated_contract_rejects_invalid_audience(
    audience: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="audience",
    ):
        AzureFederatedIdentityConfig(
            role_arn=ROLE_ARN,
            audience=audience,
            managed_identity_client_id=(CLIENT_ID),
            role_session_name=("casemesh-api"),
        )


@pytest.mark.parametrize(
    "client_id",
    (
        "",
        "not-a-uuid",
        "{11111111-1111-1111-1111-111111111111}",
    ),
)
def test_federated_contract_rejects_invalid_managed_identity_client_id(
    client_id: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="client ID",
    ):
        AzureFederatedIdentityConfig(
            role_arn=ROLE_ARN,
            audience=AUDIENCE,
            managed_identity_client_id=(client_id),
            role_session_name=("casemesh-api"),
        )


@pytest.mark.parametrize(
    "session_name",
    (
        "",
        "x",
        "contains spaces",
        "x" * 65,
    ),
)
def test_federated_contract_rejects_invalid_role_session_name(
    session_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="session name",
    ):
        AzureFederatedIdentityConfig(
            role_arn=ROLE_ARN,
            audience=AUDIENCE,
            managed_identity_client_id=(CLIENT_ID),
            role_session_name=(session_name),
        )


def test_identity_contract_module_is_zero_network() -> None:
    sys.modules.pop(
        "boto3",
        None,
    )

    sys.modules.pop(
        "botocore.config",
        None,
    )

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_identity_mode=("azure_federated"),
        aws_federated_role_arn=(ROLE_ARN),
        aws_federated_audience=(AUDIENCE),
        azure_managed_identity_client_id=(CLIENT_ID),
    )

    config = build_aws_identity_config(settings)

    assert config is not None

    assert "boto3" not in sys.modules

    assert "botocore.config" not in sys.modules
