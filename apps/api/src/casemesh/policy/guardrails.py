from dataclasses import dataclass
from typing import Literal

PolicyDecision = Literal[
    "allow",
    "require_approval",
    "block",
]

RiskLevel = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


@dataclass(
    frozen=True,
    slots=True,
)
class PolicyEvaluation:
    decision: PolicyDecision
    risk_level: RiskLevel
    requires_human_approval: bool
    rationale: str


class PolicyGuard:
    _RISK_TRIGGER_RATIONALE = (
        "A deterministic action risk trigger requires explicit human approval."
    )

    _KNOWN_ACTIONS = {
        "issue_sla_credit",
        "send_customer_notification",
        "update_case_status",
        "create_internal_note",
    }

    _SECOND_REVIEW_RATIONALE = (
        "The investigation's independent second-review gate "
        "requires explicit human approval before this action "
        "can proceed."
    )

    def __init__(
        self,
        *,
        allow_internal_note_without_review: bool = True,
    ) -> None:
        self._allow_internal_note_without_review = allow_internal_note_without_review

    def evaluate(
        self,
        *,
        action_type: str,
        payload: dict[str, object],
        investigation_confidence: str | None,
        investigation_abstained: bool,
        citation_count: int,
        second_review_requires_human: bool = False,
        risk_trigger_requires_human: bool = False,
    ) -> PolicyEvaluation:
        """Evaluate authoritative policy and apply stricter review signals.

        The CaseMesh base policy remains authoritative. Independent review
        signals and deterministic action-risk triggers may only make an
        otherwise non-blocked decision stricter. Neither signal can turn a
        block into approval or otherwise authorize an action.
        """

        base_evaluation = self._evaluate_base(
            action_type=action_type,
            payload=payload,
            investigation_confidence=(investigation_confidence),
            investigation_abstained=(investigation_abstained),
            citation_count=citation_count,
        )

        if base_evaluation.decision == "block":
            return base_evaluation

        escalation_reasons: list[str] = []

        if second_review_requires_human:
            escalation_reasons.append(self._SECOND_REVIEW_RATIONALE)

        if risk_trigger_requires_human:
            escalation_reasons.append(self._RISK_TRIGGER_RATIONALE)

        if not escalation_reasons:
            return base_evaluation

        return PolicyEvaluation(
            decision="require_approval",
            risk_level=base_evaluation.risk_level,
            requires_human_approval=True,
            rationale=(f"{base_evaluation.rationale} {' '.join(escalation_reasons)}"),
        )

    def _evaluate_base(
        self,
        *,
        action_type: str,
        payload: dict[str, object],
        investigation_confidence: str | None,
        investigation_abstained: bool,
        citation_count: int,
    ) -> PolicyEvaluation:
        if action_type not in self._KNOWN_ACTIONS:
            return PolicyEvaluation(
                decision="block",
                risk_level="high",
                requires_human_approval=False,
                rationale=(
                    f"Unknown action type '{action_type}'. The action is denied by default."
                ),
            )

        if action_type == "create_internal_note":
            if not self._allow_internal_note_without_review:
                return PolicyEvaluation(
                    decision="require_approval",
                    risk_level="low",
                    requires_human_approval=True,
                    rationale=("Internal note creation is configured to require review."),
                )

            return PolicyEvaluation(
                decision="allow",
                risk_level="low",
                requires_human_approval=False,
                rationale=(
                    "Creating an internal note is non-external "
                    "and reversible. The policy allows it "
                    "without human review."
                ),
            )

        if action_type == "issue_sla_credit":
            credit_percent = payload.get("credit_percent")

            if not self._valid_credit_percent(credit_percent):
                return PolicyEvaluation(
                    decision="block",
                    risk_level="critical",
                    requires_human_approval=False,
                    rationale=(
                        "SLA credit actions require numeric "
                        "credit_percent greater than 0 and "
                        "no more than 100."
                    ),
                )

            if (
                investigation_abstained
                or investigation_confidence
                in {
                    None,
                    "low",
                }
                or citation_count < 1
            ):
                return PolicyEvaluation(
                    decision="block",
                    risk_level="critical",
                    requires_human_approval=False,
                    rationale=(
                        "A financial SLA credit cannot be proposed "
                        "from abstained, low-confidence, or "
                        "uncited evidence."
                    ),
                )

            return PolicyEvaluation(
                decision="require_approval",
                risk_level="critical",
                requires_human_approval=True,
                rationale=(
                    "SLA credits are financially consequential "
                    "external actions and always require explicit "
                    "human approval."
                ),
            )

        if action_type == "send_customer_notification":
            if investigation_abstained or citation_count < 1:
                return PolicyEvaluation(
                    decision="block",
                    risk_level="high",
                    requires_human_approval=False,
                    rationale=(
                        "Customer-facing communication requires "
                        "at least one grounded citation and a "
                        "non-abstained investigation."
                    ),
                )

            return PolicyEvaluation(
                decision="require_approval",
                risk_level="high",
                requires_human_approval=True,
                rationale=(
                    "Customer-facing communication can create "
                    "contractual or reputational impact and "
                    "requires human review."
                ),
            )

        target_status = payload.get("status")

        if (
            not isinstance(
                target_status,
                str,
            )
            or not target_status.strip()
        ):
            return PolicyEvaluation(
                decision="block",
                risk_level="high",
                requires_human_approval=False,
                rationale=("Case status updates require a non-empty 'status' value."),
            )

        return PolicyEvaluation(
            decision="require_approval",
            risk_level="high",
            requires_human_approval=True,
            rationale=(
                "Changing case state affects operational workflow "
                "and requires explicit human approval."
            ),
        )

    @staticmethod
    def _valid_credit_percent(
        value: object,
    ) -> bool:
        if isinstance(
            value,
            bool,
        ):
            return False

        if not isinstance(
            value,
            (
                int,
                float,
            ),
        ):
            return False

        numeric = float(value)

        return 0 < numeric <= 100
