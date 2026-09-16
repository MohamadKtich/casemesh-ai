from dataclasses import dataclass
from typing import Literal

from casemesh.intelligence.contracts import (
    ReviewRoute,
    SecondReviewResult,
)

SecondReviewGateReason = Literal[
    "provider_requested_human_review",
    "review_disagreed",
    "review_uncertain",
    "high_risk_review",
    "critical_risk_review",
]


@dataclass(
    frozen=True,
    slots=True,
)
class SecondReviewGateDecision:
    """Conservative routing decision derived from a second review.

    This decision never authorizes action execution. A continue route
    means only that processing may proceed to the authoritative
    CaseMesh policy layer.
    """

    effective_route: ReviewRoute
    provider_route: ReviewRoute
    forced_human_review: bool
    reason_codes: tuple[
        SecondReviewGateReason,
        ...,
    ]

    @property
    def can_continue_to_policy(
        self,
    ) -> bool:
        """Whether the review may continue to policy evaluation."""

        return self.effective_route == "continue"


def evaluate_second_review(
    review: SecondReviewResult,
) -> SecondReviewGateDecision:
    """Apply CaseMesh conservative routing rules to a second review."""

    reasons: list[SecondReviewGateReason] = []

    if review.recommended_route == "human_review":
        reasons.append("provider_requested_human_review")

    if review.agreement == "disagree":
        reasons.append("review_disagreed")

    elif review.agreement == "uncertain":
        reasons.append("review_uncertain")

    if review.risk_level == "high":
        reasons.append("high_risk_review")

    elif review.risk_level == "critical":
        reasons.append("critical_risk_review")

    effective_route: ReviewRoute = "human_review" if reasons else "continue"

    forced_human_review = (
        effective_route == "human_review" and review.recommended_route != "human_review"
    )

    return SecondReviewGateDecision(
        effective_route=effective_route,
        provider_route=review.recommended_route,
        forced_human_review=forced_human_review,
        reason_codes=tuple(reasons),
    )
