"""Deterministic SLA calculation and business-resolution service."""

import math
from datetime import date, timedelta

from casemesh.schemas.sla import (
    SlaBusinessResolution,
    SlaCalculation,
    SlaResolutionFacts,
)

CREDIT_TOLERANCE = 1e-6

type CreditTier = tuple[float, float, float]


CREDIT_SCHEDULES: dict[float, tuple[CreditTier, ...]] = {
    99.99: (
        (99.90, 99.99, 10.0),
        (99.00, 99.90, 30.0),
        (0.00, 99.00, 100.0),
    ),
    99.95: (
        (99.50, 99.95, 10.0),
        (99.00, 99.50, 25.0),
        (0.00, 99.00, 50.0),
    ),
    99.90: (
        (99.00, 99.90, 10.0),
        (95.00, 99.00, 25.0),
        (0.00, 95.00, 50.0),
    ),
    99.50: (
        (95.00, 99.50, 10.0),
        (90.00, 95.00, 25.0),
        (0.00, 90.00, 50.0),
    ),
}


def calculate_monthly_uptime(
    *,
    total_billable_minutes: int,
    covered_downtime_minutes: int,
) -> float:
    """Calculate unrounded Monthly Uptime Percentage."""

    if total_billable_minutes <= 0:
        raise ValueError("total_billable_minutes must be greater than zero.")

    if covered_downtime_minutes < 0:
        raise ValueError("covered_downtime_minutes cannot be negative.")

    if covered_downtime_minutes > total_billable_minutes:
        raise ValueError(
            "covered_downtime_minutes cannot exceed total_billable_minutes."
        )

    return (
        (total_billable_minutes - covered_downtime_minutes)
        / total_billable_minutes
        * 100
    )


def calculate_service_credit(
    *,
    sla_target_pct: float,
    monthly_uptime_unrounded_pct: float,
) -> float:
    """Resolve the contract credit tier using unrounded uptime."""

    target = _supported_target(sla_target_pct)

    if monthly_uptime_unrounded_pct >= target:
        return 0.0

    for lower, upper, credit_pct in CREDIT_SCHEDULES[target]:
        if lower <= monthly_uptime_unrounded_pct < upper:
            return credit_pct

    return 0.0


def calculate_sla(facts: SlaResolutionFacts) -> SlaCalculation:
    """Calculate covered downtime, uptime, and eligible service credit."""

    covered_downtime = (
        facts.raw_downtime_minutes
        - facts.excluded_downtime_minutes
    )

    uptime = calculate_monthly_uptime(
        total_billable_minutes=facts.total_billable_minutes,
        covered_downtime_minutes=covered_downtime,
    )

    credit = calculate_service_credit(
        sla_target_pct=facts.sla_target_pct,
        monthly_uptime_unrounded_pct=uptime,
    )

    return SlaCalculation(
        covered_downtime_minutes=covered_downtime,
        monthly_uptime_unrounded_pct=uptime,
        monthly_uptime_pct=round(uptime, 4),
        eligible_credit_pct=credit,
    )


def resolve_sla_claim(
    facts: SlaResolutionFacts,
) -> SlaBusinessResolution:
    """Resolve an SLA credit claim without reading evaluation ground truth."""

    security_reasons = _security_reason_codes(facts)

    if not facts.machine_readable_evidence_available:
        return SlaBusinessResolution(
            decision="insufficient_evidence",
            recommended_credit_pct=None,
            requires_human_review=True,
            confidence="low",
            abstained=True,
            reason_codes=[
                "INSUFFICIENT_MACHINE_READABLE_EVIDENCE",
                *security_reasons,
            ],
            calculation=None,
        )

    if facts.evidence_conflict:
        return SlaBusinessResolution(
            decision="human_review",
            recommended_credit_pct=None,
            requires_human_review=True,
            confidence="medium",
            abstained=False,
            reason_codes=[
                "CONFLICTING_EVIDENCE",
                *security_reasons,
            ],
            calculation=None,
        )

    if facts.interpretation_ambiguous:
        return SlaBusinessResolution(
            decision="human_review",
            recommended_credit_pct=None,
            requires_human_review=True,
            confidence="medium",
            abstained=False,
            reason_codes=[
                "AMBIGUOUS_INTERPRETATION",
                *security_reasons,
            ],
            calculation=None,
        )

    if facts.claim_based_only_on_excluded_downtime:
        return SlaBusinessResolution(
            decision="deny",
            recommended_credit_pct=0.0,
            requires_human_review=False,
            confidence="high",
            abstained=False,
            reason_codes=[
                "CLAIM_BASED_ONLY_ON_EXCLUDED_DOWNTIME",
                *security_reasons,
            ],
            calculation=None,
        )

    calculation = calculate_sla(facts)

    if _claim_is_late(facts):
        return SlaBusinessResolution(
            decision="human_review",
            recommended_credit_pct=None,
            requires_human_review=True,
            confidence="medium",
            abstained=False,
            reason_codes=[
                "LATE_CLAIM",
                *security_reasons,
            ],
            calculation=calculation,
        )

    eligible = calculation.eligible_credit_pct
    requested = facts.requested_credit_pct

    if math.isclose(eligible, 0.0, abs_tol=CREDIT_TOLERANCE):
        return SlaBusinessResolution(
            decision="deny",
            recommended_credit_pct=0.0,
            requires_human_review=False,
            confidence="high",
            abstained=False,
            reason_codes=[
                "NO_SLA_BREACH",
                *security_reasons,
            ],
            calculation=calculation,
        )

    if requested > eligible + CREDIT_TOLERANCE:
        return SlaBusinessResolution(
            decision="approve_partial",
            recommended_credit_pct=eligible,
            requires_human_review=False,
            confidence="high",
            abstained=False,
            reason_codes=[
                "REQUEST_EXCEEDS_ELIGIBLE_CREDIT",
                *security_reasons,
            ],
            calculation=calculation,
        )

    if requested < eligible - CREDIT_TOLERANCE:
        return SlaBusinessResolution(
            decision="approve_requested",
            recommended_credit_pct=requested,
            requires_human_review=False,
            confidence="high",
            abstained=False,
            reason_codes=[
                "REQUEST_BELOW_ELIGIBLE_CREDIT",
                *security_reasons,
            ],
            calculation=calculation,
        )

    return SlaBusinessResolution(
        decision="approve",
        recommended_credit_pct=eligible,
        requires_human_review=False,
        confidence="high",
        abstained=False,
        reason_codes=[
            "REQUEST_MATCHES_ELIGIBLE_CREDIT",
            *security_reasons,
        ],
        calculation=calculation,
    )


def _supported_target(value: float) -> float:
    for target in CREDIT_SCHEDULES:
        if math.isclose(value, target, abs_tol=1e-9):
            return target

    raise ValueError(f"Unsupported SLA target: {value}")


def _claim_is_late(facts: SlaResolutionFacts) -> bool:
    year_text, month_text = facts.claim_month.split("-", maxsplit=1)
    year = int(year_text)
    month = int(month_text)

    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    month_end = next_month - timedelta(days=1)
    deadline = month_end + timedelta(days=facts.claim_window_days)

    return facts.submitted_at.date() > deadline


def _security_reason_codes(
    facts: SlaResolutionFacts,
) -> list[str]:
    if "prompt_injection_in_evidence" in facts.security_flags:
        return ["PROMPT_INJECTION_IGNORED"]

    return []
