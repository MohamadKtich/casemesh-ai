from casemesh.intelligence.risk_triggers import (
    RiskTriggerContext,
    RiskTriggerEngine,
)


def _evaluate(
    **kwargs: object,
):
    engine = RiskTriggerEngine()

    return engine.evaluate(
        RiskTriggerContext(
            **kwargs,
        )
    )


def test_empty_context_does_not_request_review() -> None:
    decision = _evaluate()

    assert decision.request_second_review is False
    assert decision.triggers == ()
    assert decision.reason_codes == ()


def test_low_findings_confidence_triggers_review() -> None:
    decision = _evaluate(
        findings_confidence="low",
    )

    assert decision.request_second_review is True
    assert decision.reason_codes == ("LOW_CONFIDENCE",)


def test_abstained_finding_maps_to_low_confidence_trigger() -> None:
    decision = _evaluate(
        findings_confidence="medium",
        findings_abstained=True,
    )

    assert decision.reason_codes == ("LOW_CONFIDENCE",)


def test_low_confidence_gap_triggers_review() -> None:
    decision = _evaluate(
        gap_codes=("LOW_CONFIDENCE",),
    )

    assert decision.reason_codes == ("LOW_CONFIDENCE",)


def test_conflicting_evidence_signal_triggers_review() -> None:
    decision = _evaluate(
        evidence_conflict=True,
    )

    assert decision.reason_codes == ("CONFLICTING_EVIDENCE",)


def test_conflicting_evidence_gap_triggers_review() -> None:
    decision = _evaluate(
        gap_codes=(" conflicting_evidence ",),
    )

    assert decision.reason_codes == ("CONFLICTING_EVIDENCE",)


def test_explicit_prompt_injection_signal_triggers_review() -> None:
    decision = _evaluate(
        prompt_injection_signal=True,
    )

    assert decision.reason_codes == ("PROMPT_INJECTION_SIGNAL",)


def test_existing_security_flag_triggers_prompt_injection_review() -> None:
    decision = _evaluate(
        security_flags=("prompt_injection_in_evidence",),
    )

    assert decision.reason_codes == ("PROMPT_INJECTION_SIGNAL",)


def test_high_risk_action_triggers_review() -> None:
    decision = _evaluate(
        action_type="send_customer_notification",
        action_risk_level="high",
    )

    assert decision.reason_codes == ("HIGH_RISK_ACTION",)


def test_critical_action_triggers_high_risk_review() -> None:
    decision = _evaluate(
        action_type="issue_sla_credit",
        action_risk_level="critical",
    )

    assert decision.reason_codes == (
        "HIGH_RISK_ACTION",
        "FINANCIAL_ACTION",
    )


def test_financial_action_triggers_even_without_policy_risk() -> None:
    decision = _evaluate(
        action_type=" issue_sla_credit ",
        action_risk_level="medium",
    )

    assert decision.reason_codes == ("FINANCIAL_ACTION",)


def test_manual_second_review_request_triggers_review() -> None:
    decision = _evaluate(
        manual_second_review_requested=True,
    )

    assert decision.reason_codes == ("MANUAL_SECOND_REVIEW_REQUEST",)


def test_benign_low_risk_action_does_not_trigger() -> None:
    decision = _evaluate(
        action_type="create_internal_note",
        action_risk_level="low",
    )

    assert decision.request_second_review is False
    assert decision.reason_codes == ()


def test_trigger_order_is_deterministic_and_deduplicated() -> None:
    decision = _evaluate(
        findings_confidence="low",
        findings_abstained=True,
        gap_codes=(
            "LOW_CONFIDENCE",
            "CONFLICTING_EVIDENCE",
        ),
        security_flags=("prompt_injection_in_evidence",),
        evidence_conflict=True,
        prompt_injection_signal=True,
        action_type="issue_sla_credit",
        action_risk_level="critical",
        manual_second_review_requested=True,
    )

    assert decision.reason_codes == (
        "LOW_CONFIDENCE",
        "CONFLICTING_EVIDENCE",
        "HIGH_RISK_ACTION",
        "PROMPT_INJECTION_SIGNAL",
        "FINANCIAL_ACTION",
        "MANUAL_SECOND_REVIEW_REQUEST",
    )

    assert len(decision.triggers) == 6


def test_reason_codes_are_immutable_tuple_projection() -> None:
    decision = _evaluate(
        findings_confidence="low",
        manual_second_review_requested=True,
    )

    assert isinstance(
        decision.reason_codes,
        tuple,
    )

    assert decision.reason_codes == (
        "LOW_CONFIDENCE",
        "MANUAL_SECOND_REVIEW_REQUEST",
    )
