from casemesh.core.config import Settings
from casemesh.integrations.aws.clients import (
    AWSClientFactory,
    Boto3AWSClientFactory,
    MockAWSClientFactory,
)
from casemesh.integrations.aws.gateway import AWSIntelligenceGateway


def build_aws_intelligence_gateway(
    settings: Settings,
    *,
    client_factory: AWSClientFactory | None = None,
) -> AWSIntelligenceGateway:
    """Build the AWS gateway using the configured client mode."""

    selected_factory = client_factory

    if selected_factory is None:
        if settings.aws_client_mode == "mock":
            selected_factory = MockAWSClientFactory()
        else:
            selected_factory = Boto3AWSClientFactory()

    return AWSIntelligenceGateway(
        settings,
        client_factory=selected_factory,
    )
