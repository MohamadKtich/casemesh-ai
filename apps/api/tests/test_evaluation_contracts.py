import pytest
from pydantic import ValidationError

from casemesh.evaluation.contracts import (
    BusinessResolution,
    EvaluationGroundTruth,
)


def _ground_truth(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_decision": "approve",
        "expected_credit_pct": 10.0,
        "actual_monthly_uptime_pct": 99.8,
        "expected_sla_target_pct": 99.9,
        "contract_eligible_credit_pct": 10.0,
        "requires_human_review": False,
        "security_flags": [],
        "forbidden_actions_before_approval": [
            "create_credit_request",
            "close_case",
            "send_customer_notification",
        ],
    }
    values.update(overrides)
    return values


def test_ground_truth_accepts_resolved_credit() -> None:
    truth = EvaluationGroundTruth.model_validate(_ground_truth())

    assert truth.expected_decision == "approve"
    assert truth.expected_credit_pct == 10.0


def test_ground_truth_rejects_credit_for_human_review() -> None:
    with pytest.raises(ValidationError):
        EvaluationGroundTruth.model_validate(
            _ground_truth(
                expected_decision="human_review",
                expected_credit_pct=10.0,
                requires_human_review=True,
            )
        )


def test_ground_truth_requires_zero_credit_for_denial() -> None:
    with pytest.raises(ValidationError):
        EvaluationGroundTruth.model_validate(
            _ground_truth(
                expected_decision="deny",
                expected_credit_pct=5.0,
            )
        )


def test_resolution_accepts_insufficient_evidence_abstention() -> None:
    resolution = BusinessResolution(
        decision="insufficient_evidence",
        recommended_credit_pct=None,
        requires_human_review=True,
        confidence="low",
        abstained=True,
        reason_codes=["INSUFFICIENT_SUPPORT"],
    )

    assert resolution.abstained is True


def test_resolution_rejects_high_confidence_abstention() -> None:
    with pytest.raises(ValidationError):
        BusinessResolution(
            decision="insufficient_evidence",
            recommended_credit_pct=None,
            requires_human_review=True,
            confidence="high",
            abstained=True,
        )
