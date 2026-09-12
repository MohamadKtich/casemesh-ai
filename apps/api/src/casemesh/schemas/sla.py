"""Structured SLA facts, calculations, and business resolutions."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

type SlaBusinessDecision = Literal[
    "approve",
    "approve_partial",
    "approve_requested",
    "deny",
    "human_review",
    "insufficient_evidence",
]

type SlaConfidence = Literal["low", "medium", "high"]


class SlaResolutionFacts(BaseModel):
    """Structured facts extracted from the claim, contract, and evidence."""

    model_config = ConfigDict(extra="forbid")

    claim_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    submitted_at: datetime
    requested_credit_pct: float = Field(ge=0, le=100)
    total_billable_minutes: int = Field(gt=0)
    raw_downtime_minutes: int = Field(ge=0)
    excluded_downtime_minutes: int = Field(ge=0)
    sla_target_pct: float = Field(gt=0, le=100)
    claim_window_days: int = Field(default=30, gt=0, le=365)
    machine_readable_evidence_available: bool = True
    evidence_conflict: bool = False
    interpretation_ambiguous: bool = False
    security_flags: list[str] = Field(default_factory=list)
    claim_based_only_on_excluded_downtime: bool = False

    @model_validator(mode="after")
    def validate_facts(self) -> Self:
        if self.submitted_at.tzinfo is None:
            raise ValueError("submitted_at must be timezone-aware.")

        if self.submitted_at.utcoffset() is None:
            raise ValueError("submitted_at must be timezone-aware.")

        if self.excluded_downtime_minutes > self.raw_downtime_minutes:
            raise ValueError(
                "excluded_downtime_minutes cannot exceed raw_downtime_minutes."
            )

        covered = (
            self.raw_downtime_minutes
            - self.excluded_downtime_minutes
        )

        if covered > self.total_billable_minutes:
            raise ValueError(
                "Covered downtime cannot exceed total billable minutes."
            )

        return self


class SlaCalculation(BaseModel):
    """Deterministic SLA calculation derived from structured facts."""

    model_config = ConfigDict(extra="forbid")

    covered_downtime_minutes: int = Field(ge=0)
    monthly_uptime_unrounded_pct: float = Field(ge=0, le=100)
    monthly_uptime_pct: float = Field(ge=0, le=100)
    eligible_credit_pct: float = Field(ge=0, le=100)


class SlaBusinessResolution(BaseModel):
    """Business resolution produced independently from benchmark labels."""

    model_config = ConfigDict(extra="forbid")

    decision: SlaBusinessDecision
    recommended_credit_pct: float | None = Field(default=None, ge=0, le=100)
    requires_human_review: bool
    confidence: SlaConfidence
    abstained: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    calculation: SlaCalculation | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        unresolved = {"human_review", "insufficient_evidence"}

        if self.decision in unresolved:
            if self.recommended_credit_pct is not None:
                raise ValueError(
                    "Unresolved decisions must not recommend a credit."
                )

            if not self.requires_human_review:
                raise ValueError(
                    "Unresolved decisions must require human review."
                )
        else:
            if self.recommended_credit_pct is None:
                raise ValueError(
                    "Resolved decisions must recommend a credit."
                )

            if self.requires_human_review:
                raise ValueError(
                    "Resolved business decisions must not require business review."
                )

        if self.decision == "deny" and self.recommended_credit_pct != 0:
            raise ValueError("Denied claims must recommend zero credit.")

        if self.decision == "insufficient_evidence" and not self.abstained:
            raise ValueError(
                "Insufficient-evidence decisions must abstain."
            )

        if self.abstained and self.confidence != "low":
            raise ValueError(
                "Abstained resolutions must use low confidence."
            )

        return self
