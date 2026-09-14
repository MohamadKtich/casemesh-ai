from casemesh.intelligence.contracts import (
    GuardrailAssessment,
    GuardrailStage,
    SafetyGuardrailProvider,
    SecondReviewProvider,
    SecondReviewRequest,
    SecondReviewResult,
)


class SecondReviewGuardrailBlockedError(RuntimeError):
    """Raised when the safety layer blocks review input or output."""

    def __init__(
        self,
        assessment: GuardrailAssessment,
    ) -> None:
        self.assessment = assessment
        self.stage = assessment.stage

        super().__init__(f"Second-review safety guardrail blocked {assessment.stage} content.")


class SecondReviewGuardrailFailureError(RuntimeError):
    """Raised when the safety provider itself cannot assess content."""

    def __init__(
        self,
        *,
        stage: GuardrailStage,
        error_type: str,
    ) -> None:
        self.stage = stage
        self.error_type = error_type

        super().__init__(f"Second-review safety guardrail failed during {stage} assessment.")


class GuardedSecondReviewProvider:
    """Compose safety assessments around one advisory reviewer."""

    def __init__(
        self,
        *,
        reviewer: SecondReviewProvider,
        guardrail: SafetyGuardrailProvider,
    ) -> None:
        self._reviewer = reviewer
        self._guardrail = guardrail

    @property
    def provider_name(self) -> str:
        return self._reviewer.provider_name

    @property
    def model_name(self) -> str:
        return self._reviewer.model_name

    async def review(
        self,
        request: SecondReviewRequest,
    ) -> SecondReviewResult:
        input_assessment = await self._assess_input(request)

        if input_assessment.blocked:
            raise SecondReviewGuardrailBlockedError(input_assessment)

        result = await self._reviewer.review(request)

        output_assessment = await self._assess_output(
            request=request,
            result=result,
        )

        if output_assessment.blocked:
            raise SecondReviewGuardrailBlockedError(output_assessment)

        return result

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "guardrail_provider": (self._guardrail.provider_name),
            "review": await self._reviewer.health(),
            "guardrail": await self._guardrail.health(),
        }

    async def _assess_input(
        self,
        request: SecondReviewRequest,
    ) -> GuardrailAssessment:
        try:
            return await self._guardrail.assess_input(request)

        except Exception as exc:
            raise SecondReviewGuardrailFailureError(
                stage="input",
                error_type=type(exc).__name__,
            ) from exc

    async def _assess_output(
        self,
        *,
        request: SecondReviewRequest,
        result: SecondReviewResult,
    ) -> GuardrailAssessment:
        try:
            return await self._guardrail.assess_output(
                request=request,
                result=result,
            )

        except Exception as exc:
            raise SecondReviewGuardrailFailureError(
                stage="output",
                error_type=type(exc).__name__,
            ) from exc
