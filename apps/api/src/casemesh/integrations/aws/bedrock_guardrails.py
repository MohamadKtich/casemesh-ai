import asyncio
import json
from collections.abc import Mapping
from typing import Literal, Protocol, cast

from casemesh.core.config import Settings
from casemesh.integrations.aws.gateway import (
    AWSIntelligenceGateway,
)
from casemesh.intelligence.contracts import (
    GuardrailAssessment,
    GuardrailDecision,
    GuardrailStage,
    SafetyGuardrailProvider,
    SecondReviewRequest,
    SecondReviewResult,
)

GuardrailContentSource = Literal[
    "INPUT",
    "OUTPUT",
]


class BedrockGuardrailClientProtocol(Protocol):
    """Minimal Bedrock Runtime ApplyGuardrail surface used by CaseMesh."""

    def apply_guardrail(
        self,
        **kwargs: object,
    ) -> object:
        """Apply one configured Bedrock Guardrail assessment."""


class BedrockGuardrailTimeoutError(TimeoutError):
    """Raised when ApplyGuardrail exceeds the caller timeout."""


class MockBedrockSafetyGuardrailProvider:
    """Deterministic, zero-network Bedrock Guardrails stand-in."""

    provider_name = "aws-bedrock-guardrails-mock"

    def __init__(
        self,
        *,
        guardrail_id: str,
        guardrail_version: str,
        input_decision: GuardrailDecision = "allow",
        input_reason_codes: tuple[str, ...] = (),
        input_message: str | None = None,
        output_decision: GuardrailDecision = "allow",
        output_reason_codes: tuple[str, ...] = (),
        output_message: str | None = None,
    ) -> None:
        normalized_id = guardrail_id.strip()
        normalized_version = guardrail_version.strip()

        if not normalized_id:
            raise ValueError("Bedrock guardrail_id must not be blank.")

        if not normalized_version:
            raise ValueError("Bedrock guardrail_version must not be blank.")

        self._guardrail_id = normalized_id
        self._guardrail_version = normalized_version

        self._input_decision = input_decision
        self._input_reason_codes = self._normalize_reason_codes(input_reason_codes)
        self._input_message = self._normalize_message(input_message)

        self._output_decision = output_decision
        self._output_reason_codes = self._normalize_reason_codes(output_reason_codes)
        self._output_message = self._normalize_message(output_message)

    @property
    def guardrail_id(self) -> str:
        return self._guardrail_id

    @property
    def guardrail_version(self) -> str:
        return self._guardrail_version

    async def assess_input(
        self,
        request: SecondReviewRequest,
    ) -> GuardrailAssessment:
        _ = (
            request.case_id,
            request.investigation_run_id,
            request.objective,
            request.primary_finding,
        )

        return GuardrailAssessment(
            provider=self.provider_name,
            stage="input",
            decision=self._input_decision,
            reason_codes=self._input_reason_codes,
            message=self._input_message,
        )

    async def assess_output(
        self,
        *,
        request: SecondReviewRequest,
        result: SecondReviewResult,
    ) -> GuardrailAssessment:
        _ = (
            request.case_id,
            request.investigation_run_id,
            result.provider,
            result.model,
            result.rationale,
        )

        return GuardrailAssessment(
            provider=self.provider_name,
            stage="output",
            decision=self._output_decision,
            reason_codes=self._output_reason_codes,
            message=self._output_message,
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "mode": "mock",
            "guardrail_id": self.guardrail_id,
            "guardrail_version": self.guardrail_version,
            "network_checked": False,
        }

    @staticmethod
    def _normalize_reason_codes(
        reason_codes: tuple[str, ...],
    ) -> tuple[str, ...]:
        normalized = tuple(reason_code.strip() for reason_code in reason_codes)

        if any(not reason_code for reason_code in normalized):
            raise ValueError("Bedrock guardrail reason_codes must not contain blank values.")

        return normalized

    @staticmethod
    def _normalize_message(
        message: str | None,
    ) -> str | None:
        if message is None:
            return None

        normalized = message.strip()

        if not normalized:
            return None

        return normalized


class BedrockSafetyGuardrailProvider:
    """Independent Bedrock Runtime ApplyGuardrail adapter."""

    provider_name = "aws-bedrock-guardrails"

    def __init__(
        self,
        *,
        client: BedrockGuardrailClientProtocol,
        guardrail_id: str,
        guardrail_version: str,
        request_timeout_seconds: float = 30.0,
    ) -> None:
        normalized_id = guardrail_id.strip()
        normalized_version = guardrail_version.strip()

        if not normalized_id:
            raise ValueError("Bedrock guardrail_id must not be blank.")

        if not normalized_version:
            raise ValueError("Bedrock guardrail_version must not be blank.")

        if request_timeout_seconds <= 0:
            raise ValueError("Bedrock guardrail request_timeout_seconds must be greater than zero.")

        self._client = client
        self._guardrail_id = normalized_id
        self._guardrail_version = normalized_version
        self._request_timeout_seconds = request_timeout_seconds

    @property
    def guardrail_id(self) -> str:
        return self._guardrail_id

    @property
    def guardrail_version(self) -> str:
        return self._guardrail_version

    async def assess_input(
        self,
        request: SecondReviewRequest,
    ) -> GuardrailAssessment:
        document = {
            "case_id": str(request.case_id),
            "investigation_run_id": str(request.investigation_run_id),
            "objective": request.objective,
            "primary_finding": request.primary_finding,
            "primary_confidence": (request.primary_confidence),
            "primary_abstained": (request.primary_abstained),
            "gap_codes": list(request.gap_codes),
            "evidence": [
                {
                    "chunk_id": str(evidence.chunk_id),
                    "document_id": str(evidence.document_id),
                    "chunk_index": (evidence.chunk_index),
                    "excerpt": evidence.excerpt,
                    "citation_label": (evidence.citation_label),
                }
                for evidence in request.evidence
            ],
        }

        return await self._assess(
            stage="input",
            source="INPUT",
            document=document,
        )

    async def assess_output(
        self,
        *,
        request: SecondReviewRequest,
        result: SecondReviewResult,
    ) -> GuardrailAssessment:
        _ = request

        document = {
            "provider": result.provider,
            "model": result.model,
            "agreement": result.agreement,
            "risk_level": result.risk_level,
            "concerns": list(result.concerns),
            "recommended_route": (result.recommended_route),
            "rationale": result.rationale,
        }

        return await self._assess(
            stage="output",
            source="OUTPUT",
            document=document,
        )

    async def health(
        self,
    ) -> dict[str, object]:
        """Return configuration health without invoking AWS."""

        return {
            "provider": self.provider_name,
            "mode": "sdk",
            "api": "apply_guardrail",
            "guardrail_id": self.guardrail_id,
            "guardrail_version": self.guardrail_version,
            "request_timeout_seconds": (self._request_timeout_seconds),
            "network_checked": False,
        }

    async def _assess(
        self,
        *,
        stage: GuardrailStage,
        source: GuardrailContentSource,
        document: Mapping[str, object],
    ) -> GuardrailAssessment:
        text = json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

        request = {
            "guardrailIdentifier": self.guardrail_id,
            "guardrailVersion": self.guardrail_version,
            "source": source,
            "content": [
                {
                    "text": {
                        "text": text,
                    }
                }
            ],
            "outputScope": "INTERVENTIONS",
        }

        try:
            raw_response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.apply_guardrail,
                    **request,
                ),
                timeout=self._request_timeout_seconds,
            )

        except TimeoutError as exc:
            raise BedrockGuardrailTimeoutError(
                f"Bedrock ApplyGuardrail exceeded {self._request_timeout_seconds} seconds."
            ) from exc

        return self._parse_response(
            raw_response,
            stage=stage,
        )

    def _parse_response(
        self,
        raw_response: object,
        *,
        stage: GuardrailStage,
    ) -> GuardrailAssessment:
        response = self._require_mapping(
            raw_response,
            label="Bedrock ApplyGuardrail response",
        )

        raw_action = response.get("action")

        if not isinstance(
            raw_action,
            str,
        ):
            raise ValueError("Bedrock ApplyGuardrail action must be a string.")

        action = raw_action.strip()

        if action == "NONE":
            decision: GuardrailDecision = "allow"
            reason_codes: tuple[str, ...] = ()

        elif action == "GUARDRAIL_INTERVENED":
            decision = "block"
            reason_codes = ("GUARDRAIL_INTERVENED",)

        else:
            raise ValueError(
                f"Bedrock ApplyGuardrail returned unsupported action: {action or '<blank>'}."
            )

        return GuardrailAssessment(
            provider=self.provider_name,
            stage=stage,
            decision=decision,
            reason_codes=reason_codes,
            message=self._response_message(response),
        )

    @classmethod
    def _response_message(
        cls,
        response: Mapping[str, object],
    ) -> str | None:
        raw_reason = response.get("actionReason")

        if raw_reason is not None:
            if not isinstance(
                raw_reason,
                str,
            ):
                raise ValueError(
                    "Bedrock ApplyGuardrail actionReason must be a string when present."
                )

            reason = raw_reason.strip()

            if reason:
                return reason

        raw_outputs = response.get("outputs")

        if raw_outputs is None:
            return None

        if not isinstance(
            raw_outputs,
            list,
        ):
            raise ValueError("Bedrock ApplyGuardrail outputs must be a list when present.")

        for raw_output in raw_outputs:
            output = cls._require_mapping(
                raw_output,
                label="Bedrock ApplyGuardrail output",
            )

            raw_text = output.get("text")

            if raw_text is None:
                continue

            if not isinstance(
                raw_text,
                str,
            ):
                raise ValueError("Bedrock ApplyGuardrail output text must be a string.")

            text = raw_text.strip()

            if text:
                return text

        return None

    @staticmethod
    def _require_mapping(
        value: object,
        *,
        label: str,
    ) -> Mapping[str, object]:
        if not isinstance(
            value,
            Mapping,
        ):
            raise ValueError(f"{label} must be a mapping.")

        return value


def build_mock_bedrock_safety_guardrail_provider(
    *,
    settings: Settings,
) -> SafetyGuardrailProvider:
    """Build deterministic guardrails without loading boto3 or AWS."""

    if not settings.aws_bedrock_guardrails_enabled:
        raise ValueError("AWS Bedrock Guardrails require aws_bedrock_guardrails_enabled=true.")

    if not settings.aws_bedrock_review_enabled:
        raise ValueError("AWS Bedrock Guardrails require aws_bedrock_review_enabled=true.")

    if settings.aws_client_mode != "mock":
        raise ValueError("Mock Bedrock Guardrails require aws_client_mode=mock.")

    guardrail_id = settings.aws_bedrock_guardrail_id.strip()
    guardrail_version = settings.aws_bedrock_guardrail_version.strip()

    if not guardrail_id:
        raise ValueError("AWS Bedrock Guardrails require aws_bedrock_guardrail_id.")

    if not guardrail_version:
        raise ValueError("AWS Bedrock Guardrails require aws_bedrock_guardrail_version.")

    return MockBedrockSafetyGuardrailProvider(
        guardrail_id=guardrail_id,
        guardrail_version=guardrail_version,
    )


def build_bedrock_safety_guardrail_provider(
    *,
    settings: Settings,
    gateway: AWSIntelligenceGateway,
) -> SafetyGuardrailProvider:
    """Build mock or SDK Guardrails behind one CaseMesh boundary."""

    if not settings.aws_bedrock_guardrails_enabled:
        raise ValueError("AWS Bedrock Guardrails require aws_bedrock_guardrails_enabled=true.")

    if settings.aws_client_mode == "mock":
        return build_mock_bedrock_safety_guardrail_provider(settings=settings)

    client = cast(
        BedrockGuardrailClientProtocol,
        gateway.bedrock_guardrails_runtime_client(),
    )

    return BedrockSafetyGuardrailProvider(
        client=client,
        guardrail_id=(settings.aws_bedrock_guardrail_id),
        guardrail_version=(settings.aws_bedrock_guardrail_version),
        request_timeout_seconds=(settings.aws_request_timeout_seconds),
    )
