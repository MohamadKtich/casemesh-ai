from uuid import UUID

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws import (
    build_aws_intelligence_gateway,
)
from casemesh.integrations.aws.textract import (
    TextractDocumentIntelligence,
    build_aws_document_intelligence_provider,
)
from casemesh.intelligence.document_intelligence import (
    DocumentIntelligenceRequest,
)
from casemesh.intelligence.staging import (
    StagedEvidenceObject,
)

TOPIC_ARN = "arn:aws:sns:eu-west-1:123456789012:AmazonTextractCaseMesh"

ROLE_ARN = "arn:aws:iam::123456789012:role/CaseMeshTextractNotificationRole"


class Client:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, object]] = []

    def start_document_text_detection(
        self,
        **kwargs: object,
    ) -> object:
        self.start_calls.append(dict(kwargs))

        return {"JobId": "synthetic-job"}

    def get_document_text_detection(
        self,
        **kwargs: object,
    ) -> object:
        return {
            "JobStatus": "SUCCEEDED",
            "DocumentMetadata": {
                "Pages": 1,
            },
            "Blocks": [],
        }


class Factory:
    def __init__(
        self,
        client: Client,
    ) -> None:
        self.client = client

    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        assert service_name == "textract"
        assert region_name == "eu-west-1"

        return self.client


def _request() -> DocumentIntelligenceRequest:
    return DocumentIntelligenceRequest(
        case_id=UUID("11111111-1111-1111-1111-111111111111"),
        investigation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        document_id=UUID("33333333-3333-3333-3333-333333333333"),
        staged=StagedEvidenceObject(
            provider="aws-s3",
            bucket="synthetic-bucket",
            object_key=("casemesh-temp/case/run/document/hash"),
            sha256="a" * 64,
            size_bytes=100,
            content_type="application/pdf",
        ),
    )


@pytest.mark.asyncio
async def test_start_includes_notification_channel_when_configured() -> None:
    client = Client()

    provider = TextractDocumentIntelligence(
        client=client,
        expected_bucket="synthetic-bucket",
        notification_topic_arn=TOPIC_ARN,
        notification_role_arn=ROLE_ARN,
    )

    await provider.start(_request())

    assert len(client.start_calls) == 1

    call = client.start_calls[0]

    assert call["NotificationChannel"] == {
        "SNSTopicArn": TOPIC_ARN,
        "RoleArn": ROLE_ARN,
    }


@pytest.mark.parametrize(
    (
        "topic",
        "role",
    ),
    [
        (
            TOPIC_ARN,
            None,
        ),
        (
            None,
            ROLE_ARN,
        ),
        (
            " ",
            ROLE_ARN,
        ),
        (
            TOPIC_ARN,
            " ",
        ),
    ],
)
def test_constructor_rejects_partial_notification_configuration(
    topic: str | None,
    role: str | None,
) -> None:
    with pytest.raises(
        ValueError,
        match="notification",
    ):
        TextractDocumentIntelligence(
            client=Client(),
            notification_topic_arn=topic,
            notification_role_arn=role,
        )


def test_sdk_factory_requires_notification_role() -> None:
    client = Client()

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket="synthetic-bucket",
        aws_textract_completion_topic_arn=TOPIC_ARN,
        aws_textract_queue_url="synthetic-queue",
    )

    gateway = build_aws_intelligence_gateway(
        settings,
        client_factory=Factory(client),
    )

    with pytest.raises(
        ValueError,
        match="aws_textract_notification_role_arn",
    ):
        build_aws_document_intelligence_provider(
            settings=settings,
            gateway=gateway,
        )


@pytest.mark.asyncio
async def test_sdk_factory_wires_notification_channel() -> None:
    client = Client()

    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="sdk",
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket="synthetic-bucket",
        aws_textract_completion_topic_arn=TOPIC_ARN,
        aws_textract_notification_role_arn=ROLE_ARN,
        aws_textract_queue_url="synthetic-queue",
    )

    gateway = build_aws_intelligence_gateway(
        settings,
        client_factory=Factory(client),
    )

    provider = build_aws_document_intelligence_provider(
        settings=settings,
        gateway=gateway,
    )

    await provider.start(_request())

    assert client.start_calls[0]["NotificationChannel"] == {
        "SNSTopicArn": TOPIC_ARN,
        "RoleArn": ROLE_ARN,
    }
