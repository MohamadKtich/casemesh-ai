import pytest

from casemesh.integrations.aws.lifecycle import (
    S3TemporaryEvidenceLifecyclePolicy,
)
from casemesh.integrations.aws.staging import (
    S3TemporaryEvidenceKeyBuilder,
)


def test_default_lifecycle_policy_expires_temp_objects_after_one_day() -> None:
    policy = S3TemporaryEvidenceLifecyclePolicy()

    assert policy.prefix == "casemesh-temp/"
    assert policy.expiration_days == 1
    assert policy.abort_incomplete_multipart_days == 1


def test_lifecycle_prefix_matches_default_key_builder() -> None:
    policy = S3TemporaryEvidenceLifecyclePolicy()
    key_builder = S3TemporaryEvidenceKeyBuilder()

    assert policy.prefix == f"{key_builder.prefix}/"


def test_lifecycle_configuration_matches_aws_shape() -> None:
    policy = S3TemporaryEvidenceLifecyclePolicy()

    assert policy.as_aws_configuration() == {
        "Rules": [
            {
                "ID": "casemesh-temporary-evidence-expiration",
                "Status": "Enabled",
                "Filter": {
                    "Prefix": "casemesh-temp/",
                },
                "Expiration": {
                    "Days": 1,
                },
                "AbortIncompleteMultipartUpload": {
                    "DaysAfterInitiation": 1,
                },
            }
        ]
    }


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        " ",
        "casemesh-temp",
        "../unsafe/",
        "unsafe/../prefix/",
        "unsafe//prefix/",
    ],
)
def test_lifecycle_policy_rejects_unsafe_prefix(
    prefix: str,
) -> None:
    with pytest.raises(ValueError):
        S3TemporaryEvidenceLifecyclePolicy(
            prefix=prefix,
        )


@pytest.mark.parametrize(
    "expiration_days",
    [
        0,
        -1,
    ],
)
def test_lifecycle_policy_requires_positive_expiration(
    expiration_days: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="expiration_days",
    ):
        S3TemporaryEvidenceLifecyclePolicy(
            expiration_days=expiration_days,
        )


@pytest.mark.parametrize(
    "abort_days",
    [
        0,
        -1,
    ],
)
def test_lifecycle_policy_requires_positive_abort_days(
    abort_days: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="abort_incomplete_multipart_days",
    ):
        S3TemporaryEvidenceLifecyclePolicy(
            abort_incomplete_multipart_days=abort_days,
        )


def test_lifecycle_rule_id_must_not_be_blank() -> None:
    with pytest.raises(
        ValueError,
        match="rule_id",
    ):
        S3TemporaryEvidenceLifecyclePolicy(
            rule_id=" ",
        )
