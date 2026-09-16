from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

ReviewAgreement = Literal[
    "agree",
    "disagree",
    "uncertain",
]

ReviewRiskLevel = Literal[
    "low",
    "medium",
    "high",
    "critical",
]

ReviewRoute = Literal[
    "continue",
    "human_review",
]

GuardrailStage = Literal[
    "input",
    "output",
]

GuardrailDecision = Literal[
    "allow",
    "block",
]


@dataclass(frozen=True, slots=True)
class ReviewEvidence:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    excerpt: str
    citation_label: str | None = None


@dataclass(frozen=True, slots=True)
class SecondReviewRequest:
    case_id: UUID
    investigation_run_id: UUID
    objective: str
    primary_finding: str
    primary_confidence: str | None
    primary_abstained: bool
    evidence: tuple[ReviewEvidence, ...]
    gap_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SecondReviewResult:
    provider: str
    model: str
    agreement: ReviewAgreement
    risk_level: ReviewRiskLevel
    concerns: tuple[str, ...]
    recommended_route: ReviewRoute
    rationale: str


@dataclass(frozen=True, slots=True)
class GuardrailAssessment:
    provider: str
    stage: GuardrailStage
    decision: GuardrailDecision
    reason_codes: tuple[str, ...]
    message: str | None = None

    @property
    def blocked(self) -> bool:
        return self.decision == "block"


class SecondReviewProvider(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the second-review provider identifier."""

    @property
    def model_name(self) -> str:
        """Return the configured second-review model identifier."""

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        """Perform an independent review of a completed primary finding."""

    async def health(self) -> dict[str, object]:
        """Return second-review provider health information."""


class SafetyGuardrailProvider(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the safety provider identifier."""

    async def assess_input(
        self,
        request: SecondReviewRequest,
    ) -> GuardrailAssessment:
        """Evaluate content before the external second-review call."""

    async def assess_output(
        self,
        *,
        request: SecondReviewRequest,
        result: SecondReviewResult,
    ) -> GuardrailAssessment:
        """Evaluate the second-review result before CaseMesh consumes it."""

    async def health(self) -> dict[str, object]:
        """Return safety-provider health information."""
