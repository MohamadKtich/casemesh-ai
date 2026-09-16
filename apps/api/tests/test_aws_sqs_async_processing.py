import re
import sys

import pytest

from casemesh.integrations.aws.sqs import (
    MockSQSAsyncQueue,
)
from casemesh.intelligence.async_processing import (
    AsyncQueueMessage,
)


def test_async_queue_message_rejects_blank_message_id() -> None:
    with pytest.raises(
        ValueError,
        match="message_id",
    ):
        AsyncQueueMessage(
            message_id=" ",
            receipt_handle="receipt",
            body="body",
        )


def test_async_queue_message_rejects_blank_receipt_handle() -> None:
    with pytest.raises(
        ValueError,
        match="receipt_handle",
    ):
        AsyncQueueMessage(
            message_id="message",
            receipt_handle=" ",
            body="body",
        )


def test_async_queue_message_rejects_blank_body() -> None:
    with pytest.raises(
        ValueError,
        match="body",
    ):
        AsyncQueueMessage(
            message_id="message",
            receipt_handle="receipt",
            body=" ",
        )


def test_async_queue_message_rejects_invalid_receive_count() -> None:
    with pytest.raises(
        ValueError,
        match="receive_count",
    ):
        AsyncQueueMessage(
            message_id="message",
            receipt_handle="receipt",
            body="body",
            receive_count=0,
        )


def test_mock_enqueue_rejects_duplicate_message_id() -> None:
    queue = MockSQSAsyncQueue()

    queue.enqueue(
        message_id="message-1",
        body='{"JobId":"job-1"}',
    )

    with pytest.raises(
        ValueError,
        match="must be unique",
    ):
        queue.enqueue(
            message_id="message-1",
            body='{"JobId":"job-2"}',
        )


@pytest.mark.asyncio
async def test_mock_receive_returns_message() -> None:
    queue = MockSQSAsyncQueue()

    queue.enqueue(
        message_id="message-1",
        body='{"JobId":"job-1"}',
    )

    messages = await queue.receive()

    assert len(messages) == 1

    message = messages[0]

    assert message.message_id == "message-1"
    assert message.body == '{"JobId":"job-1"}'
    assert message.receive_count == 1

    assert re.fullmatch(
        r"[a-f0-9]{64}",
        message.receipt_handle,
    )


@pytest.mark.asyncio
async def test_mock_receipt_handle_is_deterministic() -> None:
    first = MockSQSAsyncQueue()
    second = MockSQSAsyncQueue()

    first.enqueue(
        message_id="message-1",
        body="synthetic-body",
    )

    second.enqueue(
        message_id="message-1",
        body="synthetic-body",
    )

    first_message = (await first.receive())[0]

    second_message = (await second.receive())[0]

    assert first_message.receipt_handle == second_message.receipt_handle


@pytest.mark.asyncio
async def test_unacknowledged_message_can_be_redelivered() -> None:
    queue = MockSQSAsyncQueue()

    queue.enqueue(
        message_id="message-1",
        body="synthetic-body",
    )

    first = (await queue.receive())[0]

    second = (await queue.receive())[0]

    assert first.message_id == second.message_id
    assert first.receipt_handle == second.receipt_handle
    assert first.receive_count == 1
    assert second.receive_count == 2


@pytest.mark.asyncio
async def test_acknowledged_message_disappears_from_receive() -> None:
    queue = MockSQSAsyncQueue()

    queue.enqueue(
        message_id="message-1",
        body="synthetic-body",
    )

    message = (await queue.receive())[0]

    await queue.acknowledge(message)

    assert await queue.receive() == ()


@pytest.mark.asyncio
async def test_acknowledge_is_idempotent_for_same_receipt() -> None:
    queue = MockSQSAsyncQueue()

    queue.enqueue(
        message_id="message-1",
        body="synthetic-body",
    )

    message = (await queue.receive())[0]

    await queue.acknowledge(message)

    await queue.acknowledge(message)

    health = await queue.health()

    assert health["acknowledged_count"] == 1


@pytest.mark.asyncio
async def test_acknowledge_rejects_wrong_receipt_handle() -> None:
    queue = MockSQSAsyncQueue()

    queue.enqueue(
        message_id="message-1",
        body="synthetic-body",
    )

    message = (await queue.receive())[0]

    wrong = AsyncQueueMessage(
        message_id=message.message_id,
        receipt_handle="wrong-receipt",
        body=message.body,
        receive_count=message.receive_count,
    )

    with pytest.raises(
        ValueError,
        match="receipt_handle",
    ):
        await queue.acknowledge(wrong)


@pytest.mark.asyncio
async def test_acknowledge_rejects_unknown_message() -> None:
    queue = MockSQSAsyncQueue()

    unknown = AsyncQueueMessage(
        message_id="unknown",
        receipt_handle="receipt",
        body="synthetic-body",
    )

    with pytest.raises(
        ValueError,
        match="Unknown mock SQS message",
    ):
        await queue.acknowledge(unknown)


@pytest.mark.asyncio
async def test_receive_honors_max_messages() -> None:
    queue = MockSQSAsyncQueue()

    for index in range(3):
        queue.enqueue(
            message_id=f"message-{index}",
            body=f"body-{index}",
        )

    messages = await queue.receive(
        max_messages=2,
    )

    assert [message.message_id for message in messages] == [
        "message-0",
        "message-1",
    ]


@pytest.mark.asyncio
async def test_receive_rejects_invalid_max_messages() -> None:
    queue = MockSQSAsyncQueue()

    with pytest.raises(
        ValueError,
        match="max_messages",
    ):
        await queue.receive(
            max_messages=11,
        )


@pytest.mark.asyncio
async def test_receive_rejects_invalid_wait_time() -> None:
    queue = MockSQSAsyncQueue()

    with pytest.raises(
        ValueError,
        match="wait_time_seconds",
    ):
        await queue.receive(
            wait_time_seconds=21,
        )


@pytest.mark.asyncio
async def test_health_is_local_and_zero_network() -> None:
    sys.modules.pop(
        "boto3",
        None,
    )

    queue = MockSQSAsyncQueue()

    queue.enqueue(
        message_id="message-1",
        body="synthetic-body",
    )

    health = await queue.health()

    assert health == {
        "provider": "aws-sqs-mock",
        "network_checked": False,
        "queued_count": 1,
        "acknowledged_count": 0,
    }

    assert "boto3" not in sys.modules
