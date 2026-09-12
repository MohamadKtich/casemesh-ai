"""Typed contracts for deterministic CaseMesh evaluation."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

type BusinessDecision = Literal[
    "approve",
    "approve_partial",
    "approve_requested",
    "deny",
    "human_review",
    "insufficient_evidence",
]

type ConfidenceLevel = Literal["low", "medium", "high"]


class EvaluationGroundTruth(BaseModel):
    """Ground truth supplied by a CaseMesh benchmark scenario."""

    model_config = ConfigDict(extra="forbid")

    expected_decision: BusinessDecision
    expected_credit_pct: float | None = Field(default=None, ge=0, le=100)
    actual_monthly_uptime_pct: float = Field(ge=0, le=100)
    expected_sla_target_pct: float = Field(ge=0, le=100)
    contract_eligible_credit_pct: float = Field(ge=0, le=100)
    requires_human_review: bool
    security_flags: list[str] = Field(default_factory=list)
    forbidden_actions_before_approval: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_credit_contract(self) -> Self:
        unresolved = {"human_review", "insufficient_evidence"}

        if self.expected_decision in unresolved:
            if self.expected_credit_pct is not None:
                raise ValueError(
                    "Unresolved decisions must not contain an expected credit."
                )
        elif self.expected_credit_pct is None:
            raise ValueError(
                "Resolved decisions must contain an expected credit."
            )

        if self.expected_decision == "deny" and self.expected_credit_pct != 0:
            raise ValueError("Denied claims must have zero expected credit.")

        return self


class EvaluationCase(BaseModel):
    """One benchmark scenario and its immutable ground truth."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str = Field(pattern=r"^EVAL-\d{4}$")
    scenario_type: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    claim_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    submitted_at: datetime
    requested_credit_pct: float = Field(ge=0, le=100)
    case_prompt: str = Field(min_length=1)
    evidence_files: list[str] = Field(default_factory=list)
    ground_truth: EvaluationGroundTruth


class BusinessResolution(BaseModel):
    """Normalized business-resolution output scored by the evaluator."""

    model_config = ConfigDict(extra="forbid")

    decision: BusinessDecision
    recommended_credit_pct: float | None = Field(default=None, ge=0, le=100)
    requires_human_review: bool
    confidence: ConfidenceLevel
    abstained: bool = False
    reason_codes: list[str] = Field(default_factory=list)

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
        elif self.recommended_credit_pct is None:
            raise ValueError(
                "Resolved decisions must recommend a credit."
            )

        if self.decision == "deny" and self.recommended_credit_pct != 0:
            raise ValueError("Denied claims must recommend zero credit.")

        if self.decision == "insufficient_evidence" and not self.abstained:
            raise ValueError(
                "Insufficient-evidence decisions must abstain."
            )

        if self.abstained and self.confidence != "low":
            raise ValueError("Abstained resolutions must use low confidence.")

        return self
