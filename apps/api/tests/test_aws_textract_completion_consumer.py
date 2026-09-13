import json

import pytest

from casemesh.integrations.aws.textract_completion_consumer import (
    TextractCompletionConsumer,
)
from casemesh.integrations.aws.textract_notifications import (
    TextractCompletionMessageParser,
)
from casemesh.intelligence.async_processing import (
    AsyncQueueMessage,
)
from casemesh.intelligence.document_intelligence import (
    DocumentIntelligenceResult,
)
from casemesh.intelligence.idempotency import (
    InMemoryCompletionIdempotencyStore,
)

TOPIC = "arn:aws:sns:eu-west-1:123456789012:casemesh-textract"

BUCKET = "synthetic-bucket"

OBJECT_KEY = "casemesh-temp/case/run/document/hash"


class RecordingQueue:
    provider_name = "recording-queue"

    def __init__(
        self,
        *,
        acknowledge_error: Exception | None = None,
    ) -> None:
        self.acknowledge_error = acknowledge_error
        self.acknowledged: list[AsyncQueueMessage] = []

    async def receive(
        self,
        *,
        max_messages: int = 1,
        wait_time_seconds: int = 0,
    ) -> tuple[AsyncQueueMessage, ...]:
        return ()

    async def acknowledge(
        self,
        message: AsyncQueueMessage,
    ) -> None:
        if self.acknowledge_error is not None:
            raise self.acknowledge_error

        self.acknowledged.append(message)

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class FakeDocumentProvider:
    provider_name = "fake-textract"

    def __init__(
        self,
        *,
        result_status: str = "succeeded",
        result_job_id: str = "job-1",
        get_error: Exception | None = None,
    ) -> None:
        self.result_status = result_status
        self.result_job_id = result_job_id
        self.get_error = get_error
        self.get_calls: list[str] = []

    async def start(
        self,
        request: object,
    ) -> object:
        raise AssertionError("start() is not used by completion consumer.")

    async def get(
        self,
        job_id: str,
    ) -> DocumentIntelligenceResult:
        self.get_calls.append(job_id)

        if self.get_error is not None:
            raise self.get_error

        return DocumentIntelligenceResult(
            provider="fake-textract",
            job_id=self.result_job_id,
            status=self.result_status,
            text=("synthetic extracted text" if self.result_status == "succeeded" else ""),
            lines=(),
            page_count=1,
        )

    async def health(
        self,
    ) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
        }


class RecordingHandler:
    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self.error = error
        self.calls: list[tuple[object, object]] = []

    async def handle(
        self,
        *,
        event: object,
        result: object,
    ) -> None:
        if self.error is not None:
            raise self.error

        self.calls.append(
            (
                event,
                result,
            )
        )


def _parser() -> TextractCompletionMessageParser:
    return TextractCompletionMessageParser(
        expected_topic_arn=TOPIC,
        expected_bucket=BUCKET,
    )


def _body(
    *,
    status: str = "SUCCEEDED",
    job_id: str = "job-1",
) -> str:
    payload = {
        "JobId": job_id,
        "Status": status,
        "API": "StartDocumentTextDetection",
        "Timestamp": 1_725_000_000_000,
        "DocumentLocation": {
            "S3Bucket": BUCKET,
            "S3ObjectName": OBJECT_KEY,
        },
    }

    return json.dumps(
        {
            "Type": "Notification",
            "MessageId": "sns-message-1",
            "TopicArn": TOPIC,
            "Message": json.dumps(payload),
        }
    )


def _message(
    *,
    status: str = "SUCCEEDED",
    job_id: str = "job-1",
    sqs_message_id: str = "sqs-message-1",
    receipt_handle: str = "receipt-1",
    receive_count: int = 1,
) -> AsyncQueueMessage:
    return AsyncQueueMessage(
        message_id=sqs_message_id,
        receipt_handle=receipt_handle,
        body=_body(
            status=status,
            job_id=job_id,
        ),
        receive_count=receive_count,
    )


def _consumer(
    *,
    queue: RecordingQueue | None = None,
    provider: FakeDocumentProvider | None = None,
    store: InMemoryCompletionIdempotencyStore | None = None,
    handler: RecordingHandler | None = None,
) -> tuple[
    TextractCompletionConsumer,
    RecordingQueue,
    FakeDocumentProvider,
    InMemoryCompletionIdempotencyStore,
    RecordingHandler,
]:
    resolved_queue = queue or RecordingQueue()

    resolved_provider = provider or FakeDocumentProvider()

    resolved_store = store or InMemoryCompletionIdempotencyStore()

    resolved_handler = handler or RecordingHandler()

    consumer = TextractCompletionConsumer(
        queue=resolved_queue,
        parser=_parser(),
        document_provider=resolved_provider,
        idempotency_store=resolved_store,
        handler=resolved_handler,
    )

    return (
        consumer,
        resolved_queue,
        resolved_provider,
        resolved_store,
        resolved_handler,
    )


@pytest.mark.asyncio
async def test_successful_completion_is_processed_then_acknowledged() -> None:
    (
        consumer,
        queue,
        provider,
        store,
        handler,
    ) = _consumer()

    message = _message()

    outcome = await consumer.process_message(message)

    assert outcome.outcome == "processed"
    assert outcome.acknowledged is True
    assert outcome.job_id == "job-1"

    assert provider.get_calls == ["job-1"]

    assert len(handler.calls) == 1
    assert queue.acknowledged == [message]

    health = await store.health()

    assert health["completed_count"] == 1
    assert health["inflight_count"] == 0


@pytest.mark.asyncio
async def test_duplicate_completion_does_not_repeat_business_processing() -> None:
    (
        consumer,
        queue,
        provider,
        _,
        handler,
    ) = _consumer()

    first = _message(
        sqs_message_id="delivery-1",
        receipt_handle="receipt-1",
        receive_count=1,
    )

    second = _message(
        sqs_message_id="delivery-2",
        receipt_handle="receipt-2",
        receive_count=2,
    )

    first_outcome = await consumer.process_message(first)

    second_outcome = await consumer.process_message(second)

    assert first_outcome.outcome == "processed"
    assert second_outcome.outcome == "duplicate"

    assert provider.get_calls == ["job-1"]

    assert len(handler.calls) == 1

    assert queue.acknowledged == [
        first,
        second,
    ]


@pytest.mark.asyncio
async def test_failed_textract_event_does_not_fetch_result() -> None:
    (
        consumer,
        queue,
        provider,
        _,
        handler,
    ) = _consumer()

    message = _message(status="FAILED")

    outcome = await consumer.process_message(message)

    assert outcome.outcome == "processed"
    assert outcome.event_status == "failed"
    assert provider.get_calls == []
    assert len(handler.calls) == 1

    _, result = handler.calls[0]

    assert result is None
    assert queue.acknowledged == [message]


@pytest.mark.asyncio
async def test_provider_failure_keeps_message_unacknowledged_and_releases_claim() -> None:
    provider = FakeDocumentProvider(get_error=RuntimeError("synthetic Textract retrieval outage"))

    store = InMemoryCompletionIdempotencyStore()

    (
        consumer,
        queue,
        _,
        _,
        handler,
    ) = _consumer(
        provider=provider,
        store=store,
    )

    message = _message()

    with pytest.raises(
        RuntimeError,
        match="synthetic Textract retrieval outage",
    ):
        await consumer.process_message(message)

    assert queue.acknowledged == []
    assert handler.calls == []

    assert await store.begin("aws-textract:job-1") == "acquired"


@pytest.mark.asyncio
async def test_handler_failure_keeps_message_unacknowledged_and_releases_claim() -> None:
    handler = RecordingHandler(error=RuntimeError("synthetic persistence outage"))

    store = InMemoryCompletionIdempotencyStore()

    (
        consumer,
        queue,
        provider,
        _,
        _,
    ) = _consumer(
        handler=handler,
        store=store,
    )

    message = _message()

    with pytest.raises(
        RuntimeError,
        match="synthetic persistence outage",
    ):
        await consumer.process_message(message)

    assert provider.get_calls == ["job-1"]

    assert queue.acknowledged == []

    assert await store.begin("aws-textract:job-1") == "acquired"


@pytest.mark.asyncio
async def test_ack_failure_does_not_repeat_completed_business_processing() -> None:
    queue = RecordingQueue(acknowledge_error=RuntimeError("synthetic SQS delete outage"))

    store = InMemoryCompletionIdempotencyStore()

    (
        consumer,
        _,
        provider,
        _,
        handler,
    ) = _consumer(
        queue=queue,
        store=store,
    )

    first = _message(
        sqs_message_id="delivery-1",
        receipt_handle="receipt-1",
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic SQS delete outage",
    ):
        await consumer.process_message(first)

    assert provider.get_calls == ["job-1"]

    assert len(handler.calls) == 1

    queue.acknowledge_error = None

    second = _message(
        sqs_message_id="delivery-2",
        receipt_handle="receipt-2",
        receive_count=2,
    )

    outcome = await consumer.process_message(second)

    assert outcome.outcome == "duplicate"

    assert provider.get_calls == ["job-1"]

    assert len(handler.calls) == 1
    assert queue.acknowledged == [second]


@pytest.mark.asyncio
async def test_success_notification_rejects_non_successful_document_result() -> None:
    provider = FakeDocumentProvider(result_status="in_progress")

    store = InMemoryCompletionIdempotencyStore()

    (
        consumer,
        queue,
        _,
        _,
        handler,
    ) = _consumer(
        provider=provider,
        store=store,
    )

    message = _message()

    with pytest.raises(
        RuntimeError,
        match="document result is not succeeded",
    ):
        await consumer.process_message(message)

    assert queue.acknowledged == []
    assert handler.calls == []

    assert await store.begin("aws-textract:job-1") == "acquired"


@pytest.mark.asyncio
async def test_success_notification_rejects_result_job_mismatch() -> None:
    provider = FakeDocumentProvider(result_job_id="different-job")

    (
        consumer,
        queue,
        _,
        _,
        handler,
    ) = _consumer(provider=provider)

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        await consumer.process_message(_message())

    assert queue.acknowledged == []
    assert handler.calls == []


@pytest.mark.asyncio
async def test_inflight_duplicate_is_not_acknowledged() -> None:
    store = InMemoryCompletionIdempotencyStore()

    await store.begin("aws-textract:job-1")

    (
        consumer,
        queue,
        provider,
        _,
        handler,
    ) = _consumer(store=store)

    outcome = await consumer.process_message(_message())

    assert outcome.outcome == "inflight"
    assert outcome.acknowledged is False

    assert provider.get_calls == []
    assert handler.calls == []
    assert queue.acknowledged == []


@pytest.mark.asyncio
async def test_parser_failure_never_acknowledges_message() -> None:
    (
        consumer,
        queue,
        provider,
        store,
        handler,
    ) = _consumer()

    invalid = AsyncQueueMessage(
        message_id="invalid-message",
        receipt_handle="invalid-receipt",
        body="{invalid-json",
    )

    with pytest.raises(
        ValueError,
        match="valid JSON",
    ):
        await consumer.process_message(invalid)

    assert provider.get_calls == []
    assert handler.calls == []
    assert queue.acknowledged == []

    health = await store.health()

    assert health["completed_count"] == 0
    assert health["inflight_count"] == 0
