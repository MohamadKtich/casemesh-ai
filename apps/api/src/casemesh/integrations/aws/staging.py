import asyncio
import hashlib
from typing import Protocol, cast

from casemesh.core.config import Settings
from casemesh.integrations.aws.gateway import AWSIntelligenceGateway
from casemesh.intelligence.staging import (
    StagedEvidenceObject,
    TemporaryEvidenceRequest,
    TemporaryEvidenceStager,
)


class S3ClientProtocol(Protocol):
    def put_object(
        self,
        **kwargs: object,
    ) -> object:
        """Upload one temporary object."""

    def delete_object(
        self,
        **kwargs: object,
    ) -> object:
        """Delete one temporary object."""


class S3TemporaryEvidenceKeyBuilder:
    """Build isolated deterministic S3 keys without user filenames."""

    def __init__(
        self,
        *,
        prefix: str = "casemesh-temp",
    ) -> None:
        normalized = prefix.strip().strip("/")

        if not normalized:
            raise ValueError("Temporary S3 key prefix must not be blank.")

        parts = normalized.split("/")

        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("Temporary S3 key prefix contains an unsafe segment.")

        self._prefix = normalized

    @property
    def prefix(self) -> str:
        return self._prefix

    def build(
        self,
        *,
        request: TemporaryEvidenceRequest,
        sha256: str,
    ) -> str:
        return (
            f"{self._prefix}/"
            f"{request.case_id}/"
            f"{request.investigation_run_id}/"
            f"{request.document_id}/"
            f"{sha256}"
        )


class MockS3TemporaryEvidenceStager:
    """Deterministic zero-network stand-in for temporary S3 staging."""

    provider_name = "aws-s3-mock"

    def __init__(
        self,
        *,
        bucket: str = "casemesh-temporary-evidence-mock",
        key_builder: S3TemporaryEvidenceKeyBuilder | None = None,
    ) -> None:
        normalized_bucket = bucket.strip()

        if not normalized_bucket:
            raise ValueError("Temporary staging bucket must not be blank.")

        self._bucket = normalized_bucket
        self._key_builder = key_builder or S3TemporaryEvidenceKeyBuilder()
        self._objects: dict[str, bytes] = {}

    async def stage(
        self,
        request: TemporaryEvidenceRequest,
    ) -> StagedEvidenceObject:
        digest = hashlib.sha256(request.content).hexdigest()

        object_key = self._key_builder.build(
            request=request,
            sha256=digest,
        )

        self._objects[object_key] = request.content

        return StagedEvidenceObject(
            provider=self.provider_name,
            bucket=self._bucket,
            object_key=object_key,
            sha256=digest,
            size_bytes=len(request.content),
            content_type=request.content_type.strip(),
        )

    async def delete(
        self,
        staged: StagedEvidenceObject,
    ) -> None:
        if staged.bucket != self._bucket:
            raise ValueError("Refusing to delete temporary evidence from a different bucket.")

        self._objects.pop(
            staged.object_key,
            None,
        )

    async def health(self) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "bucket": self._bucket,
            "network_checked": False,
            "temporary": True,
            "object_count": len(self._objects),
        }


class S3TemporaryEvidenceStager:
    """Real S3-backed temporary evidence staging adapter."""

    provider_name = "aws-s3"
    server_side_encryption = "AES256"

    def __init__(
        self,
        *,
        client: S3ClientProtocol,
        bucket: str,
        key_builder: S3TemporaryEvidenceKeyBuilder | None = None,
    ) -> None:
        normalized_bucket = bucket.strip()

        if not normalized_bucket:
            raise ValueError("Temporary staging bucket must not be blank.")

        self._client = client
        self._bucket = normalized_bucket
        self._key_builder = key_builder or S3TemporaryEvidenceKeyBuilder()

    async def stage(
        self,
        request: TemporaryEvidenceRequest,
    ) -> StagedEvidenceObject:
        digest = hashlib.sha256(request.content).hexdigest()

        object_key = self._key_builder.build(
            request=request,
            sha256=digest,
        )

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=object_key,
            Body=request.content,
            ContentType=request.content_type.strip(),
            ServerSideEncryption=self.server_side_encryption,
            Metadata={
                "casemesh-temporary": "true",
                "sha256": digest,
            },
        )

        return StagedEvidenceObject(
            provider=self.provider_name,
            bucket=self._bucket,
            object_key=object_key,
            sha256=digest,
            size_bytes=len(request.content),
            content_type=request.content_type.strip(),
        )

    async def delete(
        self,
        staged: StagedEvidenceObject,
    ) -> None:
        self._validate_owned_object(staged)

        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=staged.object_key,
        )

    async def health(self) -> dict[str, object]:
        """Return local adapter state without performing an AWS request."""

        return {
            "provider": self.provider_name,
            "bucket": self._bucket,
            "network_checked": False,
            "temporary": True,
            "server_side_encryption": self.server_side_encryption,
        }

    def _validate_owned_object(
        self,
        staged: StagedEvidenceObject,
    ) -> None:
        if staged.provider != self.provider_name:
            raise ValueError("Refusing to delete temporary evidence from a different provider.")

        if staged.bucket != self._bucket:
            raise ValueError("Refusing to delete temporary evidence from a different bucket.")

        required_prefix = f"{self._key_builder.prefix}/"

        if not staged.object_key.startswith(required_prefix):
            raise ValueError("Refusing to delete temporary evidence outside the managed prefix.")


def build_aws_temporary_evidence_stager(
    *,
    settings: Settings,
    gateway: AWSIntelligenceGateway,
) -> TemporaryEvidenceStager:
    """Build temporary S3 staging according to the configured AWS client mode."""

    if not settings.aws_textract_enabled:
        raise ValueError("AWS temporary evidence staging requires aws_textract_enabled=true.")

    if settings.aws_client_mode == "mock":
        return MockS3TemporaryEvidenceStager(
            bucket=settings.aws_textract_bucket,
        )

    client = cast(
        S3ClientProtocol,
        gateway.s3_staging_client(),
    )

    return S3TemporaryEvidenceStager(
        client=client,
        bucket=settings.aws_textract_bucket,
    )
