from casemesh.core.config import Settings
from casemesh.integrations.aws.clients import (
    AWSClientFactory,
)
from casemesh.integrations.aws.federated_credentials import build_aws_client_factory
from casemesh.integrations.aws.gateway import AWSIntelligenceGateway


def build_aws_intelligence_gateway(
    settings: Settings,
    *,
    client_factory: AWSClientFactory | None = None,
) -> AWSIntelligenceGateway:
    """Build the AWS gateway using the configured client and identity mode."""

    selected_factory = client_factory

    if selected_factory is None:
        selected_factory = build_aws_client_factory(settings)

    return AWSIntelligenceGateway(
        settings,
        client_factory=selected_factory,
    )
