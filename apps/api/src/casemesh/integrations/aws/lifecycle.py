import asyncio
from dataclasses import dataclass
from typing import Protocol, cast

from casemesh.core.config import Settings
from casemesh.integrations.aws.gateway import AWSIntelligenceGateway


class S3LifecycleClientProtocol(Protocol):
    def put_bucket_lifecycle_configuration(
        self,
        **kwargs: object,
    ) -> object:
        """Apply lifecycle configuration to an S3 bucket."""


@dataclass(frozen=True, slots=True)
class S3TemporaryEvidenceLifecyclePolicy:
    """Lifecycle contract for the temporary CaseMesh S3 prefix."""

    prefix: str = "casemesh-temp/"
    expiration_days: int = 1
    abort_incomplete_multipart_days: int = 1
    rule_id: str = "casemesh-temporary-evidence-expiration"

    def __post_init__(self) -> None:
        normalized = self.prefix.strip()

        if not normalized:
            raise ValueError("Temporary lifecycle prefix must not be blank.")

        if not normalized.endswith("/"):
            raise ValueError("Temporary lifecycle prefix must end with '/'.")

        parts = normalized.rstrip("/").split("/")

        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("Temporary lifecycle prefix contains an unsafe segment.")

        if self.expiration_days <= 0:
            raise ValueError("expiration_days must be greater than zero.")

        if self.abort_incomplete_multipart_days <= 0:
            raise ValueError("abort_incomplete_multipart_days must be greater than zero.")

        if not self.rule_id.strip():
            raise ValueError("Lifecycle rule_id must not be blank.")

    def as_aws_configuration(self) -> dict[str, object]:
        """Return the AWS S3 lifecycle configuration payload."""

        return {
            "Rules": [
                {
                    "ID": self.rule_id,
                    "Status": "Enabled",
                    "Filter": {
                        "Prefix": self.prefix,
                    },
                    "Expiration": {
                        "Days": self.expiration_days,
                    },
                    "AbortIncompleteMultipartUpload": {
                        "DaysAfterInitiation": (self.abort_incomplete_multipart_days),
                    },
                }
            ]
        }


class MockS3TemporaryEvidenceLifecycleManager:
    """Zero-network lifecycle manager for deterministic development."""

    provider_name = "aws-s3-lifecycle-mock"

    def __init__(
        self,
        *,
        bucket: str,
        policy: S3TemporaryEvidenceLifecyclePolicy | None = None,
    ) -> None:
        normalized_bucket = bucket.strip()

        if not normalized_bucket:
            raise ValueError("Lifecycle bucket must not be blank.")

        self._bucket = normalized_bucket
        self._policy = policy or S3TemporaryEvidenceLifecyclePolicy()
        self._applied = False

    async def apply(self) -> dict[str, object]:
        self._applied = True
        return self._policy.as_aws_configuration()

    async def health(self) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "bucket": self._bucket,
            "network_checked": False,
            "applied": self._applied,
            "prefix": self._policy.prefix,
            "expiration_days": self._policy.expiration_days,
        }


class S3TemporaryEvidenceLifecycleManager:
    """Apply the temporary evidence lifecycle policy through S3."""

    provider_name = "aws-s3-lifecycle"

    def __init__(
        self,
        *,
        client: S3LifecycleClientProtocol,
        bucket: str,
        policy: S3TemporaryEvidenceLifecyclePolicy | None = None,
    ) -> None:
        normalized_bucket = bucket.strip()

        if not normalized_bucket:
            raise ValueError("Lifecycle bucket must not be blank.")

        self._client = client
        self._bucket = normalized_bucket
        self._policy = policy or S3TemporaryEvidenceLifecyclePolicy()

    async def apply(self) -> dict[str, object]:
        configuration = self._policy.as_aws_configuration()

        await asyncio.to_thread(
            self._client.put_bucket_lifecycle_configuration,
            Bucket=self._bucket,
            LifecycleConfiguration=configuration,
        )

        return configuration

    async def health(self) -> dict[str, object]:
        """Return local configuration state without contacting AWS."""

        return {
            "provider": self.provider_name,
            "bucket": self._bucket,
            "network_checked": False,
            "prefix": self._policy.prefix,
            "expiration_days": self._policy.expiration_days,
        }


def build_aws_s3_lifecycle_manager(
    *,
    settings: Settings,
    gateway: AWSIntelligenceGateway,
) -> MockS3TemporaryEvidenceLifecycleManager | S3TemporaryEvidenceLifecycleManager:
    """Build the temporary evidence lifecycle manager."""

    if not settings.aws_textract_enabled:
        raise ValueError("AWS temporary evidence lifecycle requires aws_textract_enabled=true.")

    if settings.aws_client_mode == "mock":
        return MockS3TemporaryEvidenceLifecycleManager(
            bucket=settings.aws_textract_bucket,
        )

    client = cast(
        S3LifecycleClientProtocol,
        gateway.s3_staging_client(),
    )

    return S3TemporaryEvidenceLifecycleManager(
        client=client,
        bucket=settings.aws_textract_bucket,
    )
