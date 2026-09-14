from dataclasses import dataclass
from typing import Literal

RiskTriggerCode = Literal[
    "LOW_CONFIDENCE",
    "CONFLICTING_EVIDENCE",
    "HIGH_RISK_ACTION",
    "PROMPT_INJECTION_SIGNAL",
    "FINANCIAL_ACTION",
    "MANUAL_SECOND_REVIEW_REQUEST",
]

RiskTriggerSource = Literal[
    "investigation",
    "security",
    "action",
    "manual",
]


@dataclass(
    frozen=True,
    slots=True,
)
class RiskTrigger:
    code: RiskTriggerCode
    source: RiskTriggerSource
    rationale: str


@dataclass(
    frozen=True,
    slots=True,
)
class RiskTriggerContext:
    """Signals available at investigation or action decision time."""

    findings_confidence: str | None = None
    findings_abstained: bool = False

    gap_codes: tuple[str, ...] = ()
    security_flags: tuple[str, ...] = ()

    evidence_conflict: bool = False
    prompt_injection_signal: bool = False

    action_type: str | None = None
    action_risk_level: str | None = None

    manual_second_review_requested: bool = False


@dataclass(
    frozen=True,
    slots=True,
)
class RiskTriggerDecision:
    request_second_review: bool
    triggers: tuple[RiskTrigger, ...]

    @property
    def reason_codes(
        self,
    ) -> tuple[RiskTriggerCode, ...]:
        return tuple(trigger.code for trigger in self.triggers)


class RiskTriggerEngine:
    """Deterministically decide whether independent review is warranted."""

    _FINANCIAL_ACTION_TYPES = frozenset(
        {
            "issue_sla_credit",
        }
    )

    _PROMPT_INJECTION_FLAGS = frozenset(
        {
            "prompt_injection_in_evidence",
            "prompt_injection_ignored",
            "prompt_injection_signal",
        }
    )

    def evaluate(
        self,
        context: RiskTriggerContext,
    ) -> RiskTriggerDecision:
        triggers: list[RiskTrigger] = []

        normalized_gap_codes = {
            value.strip().upper() for value in context.gap_codes if value.strip()
        }

        normalized_security_flags = {
            value.strip().lower() for value in context.security_flags if value.strip()
        }

        confidence = (
            context.findings_confidence.strip().lower()
            if isinstance(
                context.findings_confidence,
                str,
            )
            else None
        )

        action_type = (
            context.action_type.strip().lower()
            if isinstance(
                context.action_type,
                str,
            )
            else None
        )

        action_risk_level = (
            context.action_risk_level.strip().lower()
            if isinstance(
                context.action_risk_level,
                str,
            )
            else None
        )

        # --------------------------------------------------------
        # 1. LOW_CONFIDENCE
        # --------------------------------------------------------

        if (
            confidence == "low"
            or context.findings_abstained
            or "LOW_CONFIDENCE" in normalized_gap_codes
        ):
            self._append_trigger(
                triggers,
                code="LOW_CONFIDENCE",
                source="investigation",
                rationale=(
                    "The primary investigation is low-confidence, "
                    "abstained, or retained a LOW_CONFIDENCE gap."
                ),
            )

        # --------------------------------------------------------
        # 2. CONFLICTING_EVIDENCE
        # --------------------------------------------------------

        if context.evidence_conflict or "CONFLICTING_EVIDENCE" in normalized_gap_codes:
            self._append_trigger(
                triggers,
                code="CONFLICTING_EVIDENCE",
                source="investigation",
                rationale=(
                    "The available evidence contains a material "
                    "conflict requiring independent review."
                ),
            )

        # --------------------------------------------------------
        # 3. HIGH_RISK_ACTION
        # --------------------------------------------------------

        if action_risk_level in {
            "high",
            "critical",
        }:
            self._append_trigger(
                triggers,
                code="HIGH_RISK_ACTION",
                source="action",
                rationale=(f"The proposed action was classified as {action_risk_level} risk."),
            )

        # --------------------------------------------------------
        # 4. PROMPT_INJECTION_SIGNAL
        # --------------------------------------------------------

        if context.prompt_injection_signal or bool(
            normalized_security_flags & self._PROMPT_INJECTION_FLAGS
        ):
            self._append_trigger(
                triggers,
                code="PROMPT_INJECTION_SIGNAL",
                source="security",
                rationale=(
                    "A prompt-injection or untrusted-instruction "
                    "signal was detected in evidence processing."
                ),
            )

        # --------------------------------------------------------
        # 5. FINANCIAL_ACTION
        # --------------------------------------------------------

        if action_type in self._FINANCIAL_ACTION_TYPES:
            self._append_trigger(
                triggers,
                code="FINANCIAL_ACTION",
                source="action",
                rationale=("The proposed action has direct financial consequences."),
            )

        # --------------------------------------------------------
        # 6. MANUAL_SECOND_REVIEW_REQUEST
        # --------------------------------------------------------

        if context.manual_second_review_requested:
            self._append_trigger(
                triggers,
                code="MANUAL_SECOND_REVIEW_REQUEST",
                source="manual",
                rationale=("A user explicitly requested an independent second review."),
            )

        return RiskTriggerDecision(
            request_second_review=bool(triggers),
            triggers=tuple(triggers),
        )

    @staticmethod
    def _append_trigger(
        triggers: list[RiskTrigger],
        *,
        code: RiskTriggerCode,
        source: RiskTriggerSource,
        rationale: str,
    ) -> None:
        if any(trigger.code == code for trigger in triggers):
            return

        triggers.append(
            RiskTrigger(
                code=code,
                source=source,
                rationale=rationale,
            )
        )
