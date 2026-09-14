from uuid import UUID

import pytest

from casemesh.alerts import AlertEvent

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")

RUN_ID = UUID("22222222-2222-2222-2222-222222222222")

ACTION_ID = UUID("33333333-3333-3333-3333-333333333333")


def test_alert_event_serializes_only_safe_fields() -> None:
    event = AlertEvent(
        event_type="APPROVAL_REQUIRED",
        severity="high",
        source="action",
        case_id=CASE_ID,
        investigation_run_id=RUN_ID,
        action_request_id=ACTION_ID,
        reason_codes=("HIGH_RISK_ACTION",),
        risk_level="high",
        status="awaiting_approval",
    )

    assert event.payload() == {
        "event_type": "APPROVAL_REQUIRED",
        "severity": "high",
        "source": "action",
        "reason_codes": [
            "HIGH_RISK_ACTION",
        ],
        "case_id": str(CASE_ID),
        "investigation_run_id": str(RUN_ID),
        "action_request_id": str(ACTION_ID),
        "risk_level": "high",
        "status": "awaiting_approval",
    }


def test_alert_contract_has_no_raw_case_content_fields() -> None:
    event = AlertEvent(
        event_type="GUARDRAIL_BLOCK",
        severity="critical",
        source="guardrail",
        case_id=CASE_ID,
        investigation_run_id=RUN_ID,
        reason_codes=("guardrail_blocked",),
    )

    payload = event.payload()

    forbidden = {
        "objective",
        "finding",
        "findings",
        "evidence",
        "prompt",
        "payload",
        "message",
        "rationale",
        "customer_message",
    }

    assert forbidden.isdisjoint(payload)


def test_alert_reason_codes_are_trimmed() -> None:
    event = AlertEvent(
        event_type=("SECOND_REVIEW_DISAGREEMENT"),
        severity="high",
        source="second_review",
        reason_codes=("  review_disagreed  ",),
    )

    assert event.reason_codes == ("review_disagreed",)


def test_blank_alert_reason_code_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="must not contain blank",
    ):
        AlertEvent(
            event_type="CROSS_CLOUD_FAILURE",
            severity="critical",
            source="aws_boundary",
            reason_codes=("",),
        )


def test_planned_high_risk_case_event_exists_only_as_contract() -> None:
    event = AlertEvent(
        event_type="HIGH_RISK_CASE",
        severity="high",
        source="second_review",
        case_id=CASE_ID,
    )

    assert event.event_type == ("HIGH_RISK_CASE")
