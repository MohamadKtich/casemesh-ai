from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ActionStatus = Literal[
    "blocked",
    "awaiting_approval",
    "approved",
    "rejected",
    "auto_approved",
    "executed",
    "failed",
]

PolicyDecision = Literal[
    "allow",
    "require_approval",
    "block",
]

RiskLevel = Literal[
    "low",
    "medium",
    "high",
    "critical",
]

ExecutionMode = Literal[
    "dry_run",
    "live",
]

ExecutionStatus = Literal[
    "simulated",
    "completed",
    "replayed",
]


class ActionProposalRequest(BaseModel):
    action_type: str = Field(
        min_length=3,
        max_length=100,
    )

    payload: dict[str, object] = Field(
        default_factory=dict
    )


class ApprovalDecisionRequest(BaseModel):
    decision: Literal[
        "approve",
        "reject",
    ]

    reviewer_ref: str = Field(
        min_length=2,
        max_length=200,
    )

    comment: str | None = Field(
        default=None,
        max_length=2000,
    )


class ActionExecutionRequest(BaseModel):
    mode: ExecutionMode = "dry_run"

    idempotency_key: str = Field(
        min_length=8,
        max_length=200,
    )

    requested_by: str = Field(
        min_length=2,
        max_length=200,
    )


class PolicyEvaluationResponse(BaseModel):
    decision: PolicyDecision
    risk_level: RiskLevel
    requires_human_approval: bool
    rationale: str


class ActionRequestResponse(BaseModel):
    action_request_id: UUID
    case_id: UUID
    investigation_run_id: UUID | None
    resolution_draft_id: UUID | None
    approval_id: UUID | None
    thread_id: str | None
    action_type: str
    status: ActionStatus
    policy: PolicyEvaluationResponse
    payload: dict[str, object]
    reviewed_payload: dict[str, object]
    approval_decision: str | None
    reviewer_ref: str | None
    approval_comment: str | None
    interrupt: dict[str, object] | None = None
    execution_enabled: bool = False
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ActionExecutionResponse(BaseModel):
    action_request_id: UUID
    case_id: UUID
    action_type: str

    mode: ExecutionMode
    status: ExecutionStatus

    idempotent_replay: bool
    external_ref: str
    external_side_effect: bool = False

    details: dict[str, object]


class AuditEventResponse(BaseModel):
    id: UUID
    case_id: UUID | None
    investigation_run_id: UUID | None
    action_request_id: UUID | None
    actor_type: str
    actor_ref: str | None
    event_type: str
    details: dict[str, object]
    created_at: datetime