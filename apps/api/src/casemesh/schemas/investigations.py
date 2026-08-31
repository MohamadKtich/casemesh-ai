from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class InvestigationStartRequest(BaseModel):
    objective: str = Field(min_length=5, max_length=2000)


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
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
