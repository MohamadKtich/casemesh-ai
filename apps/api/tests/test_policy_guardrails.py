from casemesh.policy.guardrails import PolicyGuard


def test_low_confidence_credit_is_blocked() -> None:
    guard = PolicyGuard()

    result = guard.evaluate(
        action_type="issue_sla_credit",
        payload={"credit_percent": 10},
        investigation_confidence="low",
        investigation_abstained=False,
        citation_count=1,
    )

    assert result.decision == "block"
    assert result.risk_level == "critical"


def test_credit_with_grounded_evidence_requires_approval() -> None:
    guard = PolicyGuard()

    result = guard.evaluate(
        action_type="issue_sla_credit",
        payload={"credit_percent": 10},
        investigation_confidence="medium",
        investigation_abstained=False,
        citation_count=1,
    )

    assert result.decision == "require_approval"
    assert result.requires_human_approval is True


def test_case_status_update_requires_approval() -> None:
    guard = PolicyGuard()

    result = guard.evaluate(
        action_type="update_case_status",
        payload={"status": "resolved"},
        investigation_confidence="low",
        investigation_abstained=False,
        citation_count=0,
    )

    assert result.decision == "require_approval"
    assert result.risk_level == "high"


def test_internal_note_can_be_allowed_without_review() -> None:
    guard = PolicyGuard(
        allow_internal_note_without_review=True,
    )

    result = guard.evaluate(
        action_type="create_internal_note",
        payload={"note": "Reviewed by analyst."},
        investigation_confidence="low",
        investigation_abstained=False,
        citation_count=0,
    )

    assert result.decision == "allow"
    assert result.requires_human_approval is False


def test_unknown_action_is_denied_by_default() -> None:
    guard = PolicyGuard()

    result = guard.evaluate(
        action_type="delete_everything",
        payload={},
        investigation_confidence="high",
        investigation_abstained=False,
        citation_count=3,
    )

    assert result.decision == "block"
