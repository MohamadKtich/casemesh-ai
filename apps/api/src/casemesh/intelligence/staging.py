from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TemporaryEvidenceRequest:
    """Evidence bytes that require temporary external processing."""

    case_id: UUID
    investigation_run_id: UUID
    document_id: UUID
    content: bytes
    content_type: str

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("Temporary evidence content must not be empty.")

        if not self.content_type.strip():
            raise ValueError("Temporary evidence content_type must not be blank.")


@dataclass(frozen=True, slots=True)
class StagedEvidenceObject:
    """Reference to temporarily staged evidence."""

    provider: str
    bucket: str
    object_key: str
    sha256: str
    size_bytes: int
    content_type: str
    temporary: bool = True


class TemporaryEvidenceStager(Protocol):
    async def stage(
        self,
        request: TemporaryEvidenceRequest,
    ) -> StagedEvidenceObject:
        """Stage evidence temporarily and return its external reference."""

    async def delete(
        self,
        staged: StagedEvidenceObject,
    ) -> None:
        """Delete previously staged temporary evidence."""

    async def health(self) -> dict[str, object]:
        """Return staging-provider health information."""
