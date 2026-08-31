from typing import TypedDict
from uuid import UUID


class InvestigationState(TypedDict, total=False):
    workflow_id: UUID
    case_id: UUID
    objective: str
    status: str
    current_step: str
    attempt: int
    max_retries: int
    search_query: str
    case_analysis: str
    plan: list[dict[str, object]]
    evidence: list[dict[str, object]]
    assessment: str
    assessment_confidence: str
    assessment_abstained: bool
    gaps: list[dict[str, object]]
    findings: str
    findings_confidence: str
    findings_abstained: bool
    citations: list[dict[str, object]]
