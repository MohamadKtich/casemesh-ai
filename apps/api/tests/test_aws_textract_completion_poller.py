import pytest

from casemesh.integrations.aws.textract_completion_consumer import (
    TextractCompletionProcessingResult,
)
from casemesh.integrations.aws.textract_completion_poller import (
    TextractCompletionPoller,
)
from casemesh.intelligence.async_processing import (
    AsyncQueueMessage,
)


def _message(
    index: int,
) -> AsyncQueueMessage:
    return AsyncQueueMessage(
        message_id=f"message-{index}",
        receipt_handle=f"receipt-{index}",
        body=f"body-{index}",
    )


class Queue:
    provider_name = "poller-test-queue"

    def __init__(
        self,
        messages: tuple[
            AsyncQueueMessage,
            ...,
        ],
    ) -> None:
        self.messages = messages
        self.receive_calls: list[tuple[int, int]] = []

    async def receive(
        self,
        *,
        max_messages: int = 1,
        wait_time_seconds: int = 0,
    ) -> tuple[
        AsyncQueueMessage,
        ...,
    ]:
        self.receive_calls.append(
            (
                max_messages,
                wait_time_seconds,
            )
        )

        return self.messages

    async def acknowledge(
        self,
        message: AsyncQueueMessage,
    ) -> None:
        raise AssertionError("Poller does not acknowledge directly.")

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
        }


class Processor:
    def __init__(
        self,
        outcomes: dict[
            str,
            str | Exception,
        ],
    ) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    async def process_message(
        self,
        message: AsyncQueueMessage,
    ) -> TextractCompletionProcessingResult:
        self.calls.append(message.message_id)

        outcome = self.outcomes[message.message_id]

        if isinstance(
            outcome,
            Exception,
        ):
            raise outcome

        return TextractCompletionProcessingResult(
            outcome=outcome,
            message_id=message.message_id,
            job_id=f"job-{message.message_id}",
            event_status="succeeded",
            acknowledged=(outcome != "inflight"),
        )


@pytest.mark.asyncio
async def test_poller_isolates_individual_message_failures() -> None:
    messages = tuple(_message(index) for index in range(4))

    queue = Queue(messages)

    processor = Processor(
        {
            "message-0": "processed",
            "message-1": RuntimeError("synthetic processing failure"),
            "message-2": "duplicate",
            "message-3": "inflight",
        }
    )

    poller = TextractCompletionPoller(
        queue=queue,
        processor=processor,
    )

    result = await poller.poll_once(
        max_messages=4,
        wait_time_seconds=20,
    )

    assert result.received_count == 4
    assert result.processed_count == 1
    assert result.duplicate_count == 1
    assert result.inflight_count == 1
    assert result.failed_count == 1

    assert result.failures[0].message_id == "message-1"
    assert result.failures[0].error_type == "RuntimeError"

    assert processor.calls == [
        "message-0",
        "message-1",
        "message-2",
        "message-3",
    ]

    assert queue.receive_calls == [
        (
            4,
            20,
        )
    ]


@pytest.mark.asyncio
async def test_empty_poll_returns_zero_counts() -> None:
    queue = Queue(())

    processor = Processor({})

    poller = TextractCompletionPoller(
        queue=queue,
        processor=processor,
    )

    result = await poller.poll_once()

    assert result.received_count == 0
    assert result.processed_count == 0
    assert result.duplicate_count == 0
    assert result.inflight_count == 0
    assert result.failed_count == 0
    assert result.failures == ()
    assert processor.calls == []


@pytest.mark.asyncio
async def test_queue_receive_failure_propagates() -> None:
    class FailingQueue(Queue):
        async def receive(
            self,
            *,
            max_messages: int = 1,
            wait_time_seconds: int = 0,
        ) -> tuple[
            AsyncQueueMessage,
            ...,
        ]:
            raise RuntimeError("synthetic SQS receive outage")

    poller = TextractCompletionPoller(
        queue=FailingQueue(()),
        processor=Processor({}),
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic SQS receive outage",
    ):
        await poller.poll_once()
