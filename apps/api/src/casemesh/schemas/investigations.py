from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class InvestigationStartRequest(BaseModel):
    objective: str = Field(min_length=5, max_length=2000)
    manual_second_review_requested: bool = False


class InvestigationEvidenceRef(BaseModel):
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    hybrid_score: float
    vector_rank: int | None
    keyword_rank: int | None
    excerpt: str


class InvestigationCitation(BaseModel):
    label: str
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    excerpt: str


class InvestigationGap(BaseModel):
    code: str
    description: str


class InvestigationPlanStep(BaseModel):
    step: int
    title: str


class InvestigationRiskTriggerSummary(BaseModel):
    second_review_requested: bool
    reason_codes: list[str] = Field(default_factory=list)


class InvestigationSecondReviewSummary(BaseModel):
    status: (
        Literal[
            "completed",
            "unavailable",
            "failed",
            "budget_exhausted",
            "guardrail_blocked",
            "guardrail_failed",
        ]
        | None
    ) = None
    agreement: Literal["agree", "disagree", "uncertain"] | None = None
    risk_level: Literal["low", "medium", "high", "critical"] | None = None
    provider_route: Literal["continue", "human_review"] | None = None
    effective_route: Literal["continue", "human_review"] | None = None
    forced_human_review: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    guardrail_decision: Literal["blocked", "failed"] | None = None


class InvestigationRunResponse(BaseModel):
    workflow_id: UUID
    case_id: UUID
    objective: str | None
    state: Literal["created", "running", "completed", "failed"]
    current_step: str | None
    attempt: int
    confidence: Literal["low", "medium", "high"] | None
    abstained: bool
    analysis: str | None
    assessment: str | None
    findings: str | None
    plan: list[InvestigationPlanStep]
    evidence: list[InvestigationEvidenceRef]
    gaps: list[InvestigationGap]
    citations: list[InvestigationCitation]
    risk_triggers: InvestigationRiskTriggerSummary | None = None
    second_review: InvestigationSecondReviewSummary | None = None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
