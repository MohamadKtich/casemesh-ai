from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from casemesh.schemas.sla import SlaResolutionFacts
from casemesh.services.sla_resolution import (
    calculate_service_credit,
    calculate_sla,
    resolve_sla_claim,
)


def _facts(**overrides: object) -> SlaResolutionFacts:
    values: dict[str, object] = {
        "claim_month": "2026-07",
        "submitted_at": datetime(2026, 8, 18, 9, tzinfo=UTC),
        "requested_credit_pct": 10.0,
        "total_billable_minutes": 44_640,
        "raw_downtime_minutes": 300,
        "excluded_downtime_minutes": 120,
        "sla_target_pct": 99.9,
        "claim_window_days": 30,
        "machine_readable_evidence_available": True,
        "evidence_conflict": False,
        "interpretation_ambiguous": False,
        "security_flags": [],
    }
    values.update(overrides)
    return SlaResolutionFacts.model_validate(values)


def test_calculation_matches_dataset_formula() -> None:
    calculation = calculate_sla(_facts())

    assert calculation.covered_downtime_minutes == 180
    assert calculation.monthly_uptime_pct == 99.5968
    assert calculation.eligible_credit_pct == 10.0


def test_excluded_downtime_does_not_reduce_uptime() -> None:
    calculation = calculate_sla(
        _facts(
            raw_downtime_minutes=90,
            excluded_downtime_minutes=90,
        )
    )

    assert calculation.covered_downtime_minutes == 0
    assert calculation.monthly_uptime_pct == 100.0
    assert calculation.eligible_credit_pct == 0.0


def test_9999_schedule_uses_correct_credit_tier() -> None:
    calculation = calculate_sla(
        _facts(
            raw_downtime_minutes=60,
            excluded_downtime_minutes=0,
            sla_target_pct=99.99,
            requested_credit_pct=30.0,
        )
    )

    assert calculation.monthly_uptime_pct == 99.8656
    assert calculation.eligible_credit_pct == 30.0


def test_service_credit_uses_unrounded_uptime() -> None:
    credit = calculate_service_credit(
        sla_target_pct=99.9,
        monthly_uptime_unrounded_pct=98.999999,
    )

    assert credit == 25.0


def test_missing_machine_readable_evidence_abstains() -> None:
    resolution = resolve_sla_claim(
        _facts(machine_readable_evidence_available=False)
    )

    assert resolution.decision == "insufficient_evidence"
    assert resolution.recommended_credit_pct is None
    assert resolution.requires_human_review is True
    assert resolution.confidence == "low"
    assert resolution.abstained is True


def test_conflicting_evidence_routes_to_human_review() -> None:
    resolution = resolve_sla_claim(
        _facts(evidence_conflict=True)
    )

    assert resolution.decision == "human_review"
    assert resolution.recommended_credit_pct is None
    assert resolution.requires_human_review is True


def test_ambiguous_interpretation_routes_to_human_review() -> None:
    resolution = resolve_sla_claim(
        _facts(interpretation_ambiguous=True)
    )

    assert resolution.decision == "human_review"
    assert "AMBIGUOUS_INTERPRETATION" in resolution.reason_codes


def test_late_claim_routes_to_human_review() -> None:
    resolution = resolve_sla_claim(
        _facts(
            submitted_at=datetime(2026, 9, 25, 9, tzinfo=UTC),
        )
    )

    assert resolution.decision == "human_review"
    assert resolution.recommended_credit_pct is None
    assert "LATE_CLAIM" in resolution.reason_codes
    assert resolution.calculation is not None


def test_claim_on_deadline_is_not_late() -> None:
    resolution = resolve_sla_claim(
        _facts(
            submitted_at=datetime(2026, 8, 30, 23, tzinfo=UTC),
        )
    )

    assert resolution.decision == "approve"


def test_no_breach_is_denied() -> None:
    resolution = resolve_sla_claim(
        _facts(
            raw_downtime_minutes=90,
            excluded_downtime_minutes=90,
            requested_credit_pct=25.0,
        )
    )

    assert resolution.decision == "deny"
    assert resolution.recommended_credit_pct == 0.0


def test_overclaim_is_partially_approved() -> None:
    resolution = resolve_sla_claim(
        _facts(requested_credit_pct=30.0)
    )

    assert resolution.decision == "approve_partial"
    assert resolution.recommended_credit_pct == 10.0


def test_underclaim_approves_requested_amount() -> None:
    resolution = resolve_sla_claim(
        _facts(requested_credit_pct=5.0)
    )

    assert resolution.decision == "approve_requested"
    assert resolution.recommended_credit_pct == 5.0


def test_matching_request_is_approved() -> None:
    resolution = resolve_sla_claim(_facts())

    assert resolution.decision == "approve"
    assert resolution.recommended_credit_pct == 10.0


def test_prompt_injection_is_ignored_as_instruction() -> None:
    resolution = resolve_sla_claim(
        _facts(
            security_flags=["prompt_injection_in_evidence"],
        )
    )

    assert resolution.decision == "approve"
    assert resolution.recommended_credit_pct == 10.0
    assert "PROMPT_INJECTION_IGNORED" in resolution.reason_codes


def test_unsupported_sla_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported SLA target"):
        resolve_sla_claim(
            _facts(sla_target_pct=98.0)
        )


def test_excluded_downtime_cannot_exceed_raw_downtime() -> None:
    with pytest.raises(ValidationError):
        _facts(
            raw_downtime_minutes=10,
            excluded_downtime_minutes=20,
        )
