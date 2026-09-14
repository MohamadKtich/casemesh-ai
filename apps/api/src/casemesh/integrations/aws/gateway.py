from dataclasses import dataclass

from casemesh.core.config import Settings
from casemesh.integrations.aws.clients import (
    AWSClientFactory,
    Boto3AWSClientFactory,
)


@dataclass(frozen=True, slots=True)
class AWSCapabilityState:
    enabled: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class AWSIntelligenceGatewayStatus:
    provider: str
    enabled: bool
    client_mode: str
    ai_region: str
    document_region: str
    second_review: AWSCapabilityState
    guardrails: AWSCapabilityState
    document_intelligence: AWSCapabilityState
    async_processing: AWSCapabilityState
    human_alerts: AWSCapabilityState
    network_checked: bool = False


class AWSClientAccessError(RuntimeError):
    """Raised when code requests a disabled AWS capability."""


class AWSIntelligenceGateway:
    """Offline-safe boundary for AWS specialized intelligence capabilities."""

    provider_name = "aws"

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: AWSClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory

    @property
    def enabled(self) -> bool:
        return self._settings.aws_intelligence_enabled

    def status(self) -> AWSIntelligenceGatewayStatus:
        return AWSIntelligenceGatewayStatus(
            provider=self.provider_name,
            enabled=self.enabled,
            client_mode=self._settings.aws_client_mode,
            ai_region=self._settings.aws_ai_region,
            document_region=self._settings.aws_document_region,
            second_review=self._capability_state(self._settings.aws_bedrock_review_enabled),
            guardrails=self._capability_state(self._settings.aws_bedrock_guardrails_enabled),
            document_intelligence=self._capability_state(self._settings.aws_textract_enabled),
            async_processing=self._capability_state(self._settings.aws_async_processing_enabled),
            human_alerts=self._capability_state(self._settings.aws_sns_alerts_enabled),
        )

    async def health(self) -> dict[str, object]:
        """Return configuration health without making network requests."""

        status = self.status()

        return {
            "provider": status.provider,
            "enabled": status.enabled,
            "client_mode": status.client_mode,
            "network_checked": status.network_checked,
            "regions": {
                "ai": status.ai_region,
                "document": status.document_region,
            },
            "capabilities": {
                "second_review": status.second_review.enabled,
                "guardrails": status.guardrails.enabled,
                "document_intelligence": (status.document_intelligence.enabled),
                "async_processing": status.async_processing.enabled,
                "human_alerts": status.human_alerts.enabled,
            },
        }

    def bedrock_runtime_client(self) -> object:
        status = self.status()

        self._require_capability(
            capability="bedrock_second_review",
            state=status.second_review,
        )

        return self._clients().create_client(
            service_name="bedrock-runtime",
            region_name=self._settings.aws_ai_region,
        )

    def bedrock_guardrails_runtime_client(self) -> object:
        """Return Bedrock Runtime only when Guardrails are enabled."""

        status = self.status()

        self._require_capability(
            capability="bedrock_guardrails",
            state=status.guardrails,
        )

        return self._clients().create_client(
            service_name="bedrock-runtime",
            region_name=self._settings.aws_ai_region,
        )

    def textract_client(self) -> object:
        status = self.status()

        self._require_capability(
            capability="textract",
            state=status.document_intelligence,
        )

        return self._clients().create_client(
            service_name="textract",
            region_name=self._settings.aws_document_region,
        )

    def s3_staging_client(self) -> object:
        status = self.status()

        self._require_capability(
            capability="s3_staging",
            state=status.document_intelligence,
        )

        return self._clients().create_client(
            service_name="s3",
            region_name=self._settings.aws_document_region,
        )

    def sqs_client(self) -> object:
        status = self.status()

        self._require_capability(
            capability="sqs_async_processing",
            state=status.async_processing,
        )

        return self._clients().create_client(
            service_name="sqs",
            region_name=self._settings.aws_document_region,
        )

    def human_alerts_sns_client(self) -> object:
        status = self.status()

        self._require_capability(
            capability="sns_human_alerts",
            state=status.human_alerts,
        )

        return self._clients().create_client(
            service_name="sns",
            region_name=self._settings.aws_ai_region,
        )

    def _clients(self) -> AWSClientFactory:
        if self._client_factory is None:
            self._client_factory = Boto3AWSClientFactory()

        return self._client_factory

    def _capability_state(
        self,
        feature_enabled: bool,
    ) -> AWSCapabilityState:
        if not self.enabled:
            return AWSCapabilityState(
                enabled=False,
                reason="master_disabled",
            )

        if not feature_enabled:
            return AWSCapabilityState(
                enabled=False,
                reason="feature_disabled",
            )

        return AWSCapabilityState(
            enabled=True,
            reason=None,
        )

    @staticmethod
    def _require_capability(
        *,
        capability: str,
        state: AWSCapabilityState,
    ) -> None:
        if state.enabled:
            return

        reason = state.reason or "unavailable"

        raise AWSClientAccessError(f"AWS capability '{capability}' is unavailable: {reason}.")
