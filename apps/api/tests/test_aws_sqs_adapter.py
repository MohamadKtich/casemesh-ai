import sys

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws import (
    AWSIntelligenceGateway,
    build_aws_intelligence_gateway,
)
from casemesh.integrations.aws.sqs import (
    MockSQSAsyncQueue,
    SQSAsyncQueue,
    build_aws_async_queue,
)
from casemesh.intelligence.async_processing import (
    AsyncQueueMessage,
)


class FakeSQSClient:
    def __init__(
        self,
        *,
        receive_response: object | None = None,
        receive_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self.receive_response = receive_response if receive_response is not None else {}

        self.receive_error = receive_error
        self.delete_error = delete_error

        self.receive_calls: list[dict[str, object]] = []

        self.delete_calls: list[dict[str, object]] = []

    def receive_message(
        self,
        **kwargs: object,
    ) -> object:
        self.receive_calls.append(dict(kwargs))

        if self.receive_error is not None:
            raise self.receive_error

        return self.receive_response

    def delete_message(
        self,
        **kwargs: object,
    ) -> object:
        self.delete_calls.append(dict(kwargs))

        if self.delete_error is not None:
            raise self.delete_error

        return {}


class FakeSQSClientFactory:
    def __init__(
        self,
        client: FakeSQSClient,
    ) -> None:
        self.client = client
        self.calls: list[tuple[str, str]] = []

    def create_client(
        self,
        *,
        service_name: str,
        region_name: str,
    ) -> object:
        self.calls.append(
            (
                service_name,
                region_name,
            )
        )

        return self.client


def _settings(
    *,
    mode: str,
) -> Settings:
    return Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode=mode,
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket="synthetic-bucket",
        aws_textract_completion_topic_arn="synthetic-topic",
        aws_textract_queue_url=("https://sqs.eu-west-1.amazonaws.com/123456789012/casemesh-test"),
    )


@pytest.mark.asyncio
async def test_real_receive_uses_expected_sqs_parameters() -> None:
    client = FakeSQSClient(
        receive_response={
            "Messages": [
                {
                    "MessageId": "message-1",
                    "ReceiptHandle": "receipt-1",
                    "Body": '{"JobId":"job-1"}',
                    "Attributes": {
                        "ApproximateReceiveCount": "3",
                    },
                }
            ]
        }
    )

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    messages = await queue.receive(
        max_messages=5,
        wait_time_seconds=20,
    )

    assert len(messages) == 1

    assert messages[0] == AsyncQueueMessage(
        message_id="message-1",
        receipt_handle="receipt-1",
        body='{"JobId":"job-1"}',
        receive_count=3,
    )

    assert client.receive_calls == [
        {
            "QueueUrl": "synthetic-queue-url",
            "MaxNumberOfMessages": 5,
            "WaitTimeSeconds": 20,
            "MessageSystemAttributeNames": ["ApproximateReceiveCount"],
        }
    ]


@pytest.mark.asyncio
async def test_receive_without_messages_returns_empty_tuple() -> None:
    client = FakeSQSClient(receive_response={})

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    assert await queue.receive() == ()


@pytest.mark.asyncio
async def test_receive_defaults_receive_count_to_one() -> None:
    client = FakeSQSClient(
        receive_response={
            "Messages": [
                {
                    "MessageId": "message-1",
                    "ReceiptHandle": "receipt-1",
                    "Body": "body",
                }
            ]
        }
    )

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    message = (await queue.receive())[0]

    assert message.receive_count == 1


@pytest.mark.asyncio
async def test_acknowledge_deletes_by_receipt_handle() -> None:
    client = FakeSQSClient()

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    message = AsyncQueueMessage(
        message_id="message-1",
        receipt_handle="latest-receipt-handle",
        body="body",
        receive_count=2,
    )

    await queue.acknowledge(message)

    assert client.delete_calls == [
        {
            "QueueUrl": "synthetic-queue-url",
            "ReceiptHandle": ("latest-receipt-handle"),
        }
    ]


@pytest.mark.asyncio
async def test_receive_api_failure_propagates() -> None:
    client = FakeSQSClient(receive_error=RuntimeError("synthetic SQS outage"))

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic SQS outage",
    ):
        await queue.receive()


@pytest.mark.asyncio
async def test_delete_api_failure_propagates() -> None:
    client = FakeSQSClient(delete_error=RuntimeError("synthetic delete outage"))

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    message = AsyncQueueMessage(
        message_id="message-1",
        receipt_handle="receipt-1",
        body="body",
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic delete outage",
    ):
        await queue.acknowledge(message)


@pytest.mark.asyncio
async def test_receive_rejects_non_mapping_response() -> None:
    client = FakeSQSClient(receive_response="invalid")

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    with pytest.raises(
        ValueError,
        match="invalid response",
    ):
        await queue.receive()


@pytest.mark.asyncio
async def test_receive_rejects_non_list_messages() -> None:
    client = FakeSQSClient(receive_response={"Messages": {"not": "a-list"}})

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    with pytest.raises(
        ValueError,
        match="Messages must be a list",
    ):
        await queue.receive()


@pytest.mark.parametrize(
    "message",
    [
        {
            "ReceiptHandle": "receipt",
            "Body": "body",
        },
        {
            "MessageId": "message",
            "Body": "body",
        },
        {
            "MessageId": "message",
            "ReceiptHandle": "receipt",
        },
    ],
)
@pytest.mark.asyncio
async def test_receive_rejects_missing_required_message_fields(
    message: dict[str, object],
) -> None:
    client = FakeSQSClient(receive_response={"Messages": [message]})

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    with pytest.raises(
        ValueError,
    ):
        await queue.receive()


@pytest.mark.parametrize(
    "raw_count",
    [
        "zero",
        "0",
        0,
        -1,
        True,
        {},
    ],
)
@pytest.mark.asyncio
async def test_receive_rejects_invalid_receive_count(
    raw_count: object,
) -> None:
    client = FakeSQSClient(
        receive_response={
            "Messages": [
                {
                    "MessageId": "message",
                    "ReceiptHandle": "receipt",
                    "Body": "body",
                    "Attributes": {
                        "ApproximateReceiveCount": raw_count,
                    },
                }
            ]
        }
    )

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    with pytest.raises(
        ValueError,
        match="ApproximateReceiveCount",
    ):
        await queue.receive()


@pytest.mark.asyncio
async def test_health_does_not_call_aws() -> None:
    client = FakeSQSClient()

    queue = SQSAsyncQueue(
        client=client,
        queue_url="synthetic-queue-url",
    )

    health = await queue.health()

    assert health == {
        "provider": "aws-sqs",
        "network_checked": False,
        "queue_configured": True,
    }

    assert client.receive_calls == []
    assert client.delete_calls == []


def test_constructor_rejects_blank_queue_url() -> None:
    client = FakeSQSClient()

    with pytest.raises(
        ValueError,
        match="queue_url",
    ):
        SQSAsyncQueue(
            client=client,
            queue_url=" ",
        )


def test_factory_returns_mock_without_boto3() -> None:
    sys.modules.pop(
        "boto3",
        None,
    )

    settings = _settings(mode="mock")

    gateway = build_aws_intelligence_gateway(settings)

    queue = build_aws_async_queue(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        queue,
        MockSQSAsyncQueue,
    )

    assert "boto3" not in sys.modules


def test_factory_uses_document_region_for_sdk_mode() -> None:
    client = FakeSQSClient()

    factory = FakeSQSClientFactory(client)

    settings = _settings(mode="sdk")

    gateway = build_aws_intelligence_gateway(
        settings,
        client_factory=factory,
    )

    queue = build_aws_async_queue(
        settings=settings,
        gateway=gateway,
    )

    assert isinstance(
        queue,
        SQSAsyncQueue,
    )

    assert factory.calls == [
        (
            "sqs",
            "eu-west-1",
        )
    ]


def test_factory_rejects_disabled_async_processing() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
    )

    gateway = AWSIntelligenceGateway(settings)

    with pytest.raises(
        ValueError,
        match="aws_async_processing_enabled=true",
    ):
        build_aws_async_queue(
            settings=settings,
            gateway=gateway,
        )
