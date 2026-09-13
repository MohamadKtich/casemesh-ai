from dataclasses import dataclass
from typing import Literal, Protocol

from casemesh.integrations.aws.textract_notifications import (
    TextractCompletionEvent,
    TextractCompletionMessageParser,
)
from casemesh.intelligence.async_processing import (
    AsyncQueue,
    AsyncQueueMessage,
)
from casemesh.intelligence.document_intelligence import (
    DocumentIntelligenceProvider,
    DocumentIntelligenceResult,
)
from casemesh.intelligence.idempotency import (
    CompletionIdempotencyStore,
)

TextractCompletionOutcome = Literal[
    "processed",
    "duplicate",
    "inflight",
]


@dataclass(frozen=True, slots=True)
class TextractCompletionProcessingResult:
    """Outcome of processing one SQS-delivered Textract completion."""

    outcome: TextractCompletionOutcome
    message_id: str
    job_id: str
    event_status: str
    acknowledged: bool


class TextractCompletionHandler(Protocol):
    """Application boundary invoked after a validated Textract completion."""

    async def handle(
        self,
        *,
        event: TextractCompletionEvent,
        result: DocumentIntelligenceResult | None,
    ) -> None:
        """Persist or route the completed Textract outcome."""


class TextractCompletionConsumer:
    """Idempotently process validated Textract completion notifications."""

    def __init__(
        self,
        *,
        queue: AsyncQueue,
        parser: TextractCompletionMessageParser,
        document_provider: DocumentIntelligenceProvider,
        idempotency_store: CompletionIdempotencyStore,
        handler: TextractCompletionHandler,
    ) -> None:
        self._queue = queue
        self._parser = parser
        self._document_provider = document_provider
        self._idempotency_store = idempotency_store
        self._handler = handler

    async def process_message(
        self,
        message: AsyncQueueMessage,
    ) -> TextractCompletionProcessingResult:
        """Process one delivery without hiding retryable failures."""

        event = self._parser.parse(message)

        decision = await self._idempotency_store.begin(event.idempotency_key)

        if decision == "completed":
            await self._queue.acknowledge(message)

            return TextractCompletionProcessingResult(
                outcome="duplicate",
                message_id=message.message_id,
                job_id=event.job_id,
                event_status=event.status,
                acknowledged=True,
            )

        if decision == "inflight":
            return TextractCompletionProcessingResult(
                outcome="inflight",
                message_id=message.message_id,
                job_id=event.job_id,
                event_status=event.status,
                acknowledged=False,
            )

        try:
            result = await self._resolve_result(event)

            await self._handler.handle(
                event=event,
                result=result,
            )

            await self._idempotency_store.complete(event.idempotency_key)

        except Exception:
            await self._idempotency_store.release(event.idempotency_key)

            raise

        await self._queue.acknowledge(message)

        return TextractCompletionProcessingResult(
            outcome="processed",
            message_id=message.message_id,
            job_id=event.job_id,
            event_status=event.status,
            acknowledged=True,
        )

    async def _resolve_result(
        self,
        event: TextractCompletionEvent,
    ) -> DocumentIntelligenceResult | None:
        if event.status == "failed":
            return None

        result = await self._document_provider.get(event.job_id)

        if result.job_id != event.job_id:
            raise ValueError(
                "Textract completion result job_id does not match notification job_id."
            )

        if result.status != "succeeded":
            raise RuntimeError(
                "Textract completion notification reported success "
                "but document result is not succeeded."
            )

        return result
