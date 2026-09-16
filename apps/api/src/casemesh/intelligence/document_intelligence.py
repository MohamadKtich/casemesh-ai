from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from casemesh.intelligence.staging import StagedEvidenceObject

DocumentIntelligenceStatus = Literal[
    "in_progress",
    "succeeded",
    "failed",
]


@dataclass(frozen=True, slots=True)
class DocumentTextLine:
    """One normalized line extracted from a document."""

    page_number: int
    text: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.page_number <= 0:
            raise ValueError("page_number must be greater than zero.")

        if not self.text.strip():
            raise ValueError("Document text line must not be blank.")

        if self.confidence is not None and not 0 <= self.confidence <= 100:
            raise ValueError("Document text confidence must be between 0 and 100.")


@dataclass(frozen=True, slots=True)
class DocumentIntelligenceRequest:
    """Request for specialized external document extraction."""

    case_id: UUID
    investigation_run_id: UUID
    document_id: UUID
    staged: StagedEvidenceObject

    def __post_init__(self) -> None:
        if not self.staged.temporary:
            raise ValueError("Document intelligence requires a temporary staged object.")


@dataclass(frozen=True, slots=True)
class DocumentIntelligenceJob:
    """Provider job reference for asynchronous document extraction."""

    provider: str
    job_id: str
    status: DocumentIntelligenceStatus

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("Document intelligence provider must not be blank.")

        if not self.job_id.strip():
            raise ValueError("Document intelligence job_id must not be blank.")


@dataclass(frozen=True, slots=True)
class DocumentIntelligenceResult:
    """Normalized document extraction result."""

    provider: str
    job_id: str
    status: DocumentIntelligenceStatus
    text: str
    lines: tuple[DocumentTextLine, ...]
    page_count: int
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("Document intelligence provider must not be blank.")

        if not self.job_id.strip():
            raise ValueError("Document intelligence job_id must not be blank.")

        if self.page_count < 0:
            raise ValueError("page_count must not be negative.")


class DocumentIntelligenceProvider(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""

    async def start(
        self,
        request: DocumentIntelligenceRequest,
    ) -> DocumentIntelligenceJob:
        """Start document extraction."""

    async def get(
        self,
        job_id: str,
    ) -> DocumentIntelligenceResult:
        """Read the current extraction result."""

    async def health(self) -> dict[str, object]:
        """Return provider health information."""
