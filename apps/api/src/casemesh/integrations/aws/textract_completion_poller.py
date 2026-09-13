from dataclasses import dataclass
from typing import Protocol

from casemesh.integrations.aws.textract_completion_consumer import (
    TextractCompletionProcessingResult,
)
from casemesh.intelligence.async_processing import (
    AsyncQueue,
    AsyncQueueMessage,
)


class TextractCompletionMessageProcessor(Protocol):
    """Process one normalized queue delivery."""

    async def process_message(
        self,
        message: AsyncQueueMessage,
    ) -> TextractCompletionProcessingResult:
        """Process one completion delivery."""


@dataclass(frozen=True, slots=True)
class TextractCompletionPollFailure:
    """Failure isolated to one SQS delivery."""

    message_id: str
    error_type: str


@dataclass(frozen=True, slots=True)
class TextractCompletionPollResult:
    """Summary of one SQS polling iteration."""

    received_count: int
    processed_count: int
    duplicate_count: int
    inflight_count: int
    failed_count: int
    failures: tuple[
        TextractCompletionPollFailure,
        ...,
    ]


class TextractCompletionPoller:
    """Poll SQS and isolate failures to individual deliveries."""

    def __init__(
        self,
        *,
        queue: AsyncQueue,
        processor: TextractCompletionMessageProcessor,
    ) -> None:
        self._queue = queue
        self._processor = processor

    async def poll_once(
        self,
        *,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
    ) -> TextractCompletionPollResult:
        messages = await self._queue.receive(
            max_messages=max_messages,
            wait_time_seconds=wait_time_seconds,
        )

        processed_count = 0
        duplicate_count = 0
        inflight_count = 0

        failures: list[TextractCompletionPollFailure] = []

        for message in messages:
            try:
                result = await self._processor.process_message(message)
            except Exception as exc:
                failures.append(
                    TextractCompletionPollFailure(
                        message_id=message.message_id,
                        error_type=type(exc).__name__,
                    )
                )

                continue

            if result.outcome == "processed":
                processed_count += 1

            elif result.outcome == "duplicate":
                duplicate_count += 1

            elif result.outcome == "inflight":
                inflight_count += 1

        return TextractCompletionPollResult(
            received_count=len(messages),
            processed_count=processed_count,
            duplicate_count=duplicate_count,
            inflight_count=inflight_count,
            failed_count=len(failures),
            failures=tuple(failures),
        )
