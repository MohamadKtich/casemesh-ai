from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CaseStatus = Literal[
    "created",
    "evidence_ready",
    "investigating",
    "pending_approval",
    "approved",
    "rejected",
    "action_executed",
    "closed",
]

CasePriority = Literal["low", "normal", "high", "critical"]


class CaseCreate(BaseModel):
    case_number: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    priority: CasePriority = "normal"
    customer_ref: str | None = Field(default=None, max_length=200)


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    customer_ref: str | None = Field(default=None, max_length=200)


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    title: str
    description: str | None
    status: str
    priority: str
    customer_ref: str | None
    created_at: datetime
    updated_at: datetime
