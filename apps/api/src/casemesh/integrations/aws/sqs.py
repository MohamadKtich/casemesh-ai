import asyncio
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from casemesh.core.config import Settings
from casemesh.integrations.aws.gateway import AWSIntelligenceGateway
from casemesh.intelligence.async_processing import (
    AsyncQueue,
    AsyncQueueMessage,
)


class SQSClientProtocol(Protocol):
    """Minimal boto3 SQS client surface required by CaseMesh."""

    def receive_message(
        self,
        **kwargs: object,
    ) -> object:
        """Receive messages from SQS."""

    def delete_message(
        self,
        **kwargs: object,
    ) -> object:
        """Delete a successfully processed SQS message."""


@dataclass(slots=True)
class _MockQueueEntry:
    message_id: str
    body: str
    receipt_handle: str
    receive_count: int = 0
    acknowledged: bool = False


class MockSQSAsyncQueue:
    """Deterministic zero-network model of the CaseMesh SQS queue."""

    provider_name = "aws-sqs-mock"

    def __init__(self) -> None:
        self._entries: list[_MockQueueEntry] = []

    def enqueue(
        self,
        *,
        message_id: str,
        body: str,
    ) -> None:
        normalized_message_id = message_id.strip()
        normalized_body = body.strip()

        if not normalized_message_id:
            raise ValueError("Mock SQS message_id must not be blank.")

        if not normalized_body:
            raise ValueError("Mock SQS body must not be blank.")

        if any(entry.message_id == normalized_message_id for entry in self._entries):
            raise ValueError("Mock SQS message_id must be unique.")

        receipt_handle = self._receipt_handle(
            message_id=normalized_message_id,
            body=normalized_body,
        )

        self._entries.append(
            _MockQueueEntry(
                message_id=normalized_message_id,
                body=normalized_body,
                receipt_handle=receipt_handle,
            )
        )

    async def receive(
        self,
        *,
        max_messages: int = 1,
        wait_time_seconds: int = 0,
    ) -> tuple[AsyncQueueMessage, ...]:
        self._validate_receive_options(
            max_messages=max_messages,
            wait_time_seconds=wait_time_seconds,
        )

        messages: list[AsyncQueueMessage] = []

        for entry in self._entries:
            if entry.acknowledged:
                continue

            entry.receive_count += 1

            messages.append(
                AsyncQueueMessage(
                    message_id=entry.message_id,
                    receipt_handle=entry.receipt_handle,
                    body=entry.body,
                    receive_count=entry.receive_count,
                )
            )

            if len(messages) >= max_messages:
                break

        return tuple(messages)

    async def acknowledge(
        self,
        message: AsyncQueueMessage,
    ) -> None:
        for entry in self._entries:
            if entry.message_id != message.message_id:
                continue

            if entry.receipt_handle != message.receipt_handle:
                raise ValueError("Mock SQS receipt_handle does not match message.")

            entry.acknowledged = True
            return

        raise ValueError("Unknown mock SQS message.")

    async def health(self) -> dict[str, object]:
        queued_count = sum(1 for entry in self._entries if not entry.acknowledged)

        acknowledged_count = sum(1 for entry in self._entries if entry.acknowledged)

        return {
            "provider": self.provider_name,
            "network_checked": False,
            "queued_count": queued_count,
            "acknowledged_count": acknowledged_count,
        }

    @staticmethod
    def _receipt_handle(
        *,
        message_id: str,
        body: str,
    ) -> str:
        seed = f"{message_id}:{body}"

        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_receive_options(
        *,
        max_messages: int,
        wait_time_seconds: int,
    ) -> None:
        validate_sqs_receive_options(
            max_messages=max_messages,
            wait_time_seconds=wait_time_seconds,
        )


class SQSAsyncQueue:
    """Real SQS queue adapter behind the AWS intelligence gateway."""

    provider_name = "aws-sqs"

    def __init__(
        self,
        *,
        client: SQSClientProtocol,
        queue_url: str,
    ) -> None:
        normalized_queue_url = queue_url.strip()

        if not normalized_queue_url:
            raise ValueError("SQS queue_url must not be blank.")

        self._client = client
        self._queue_url = normalized_queue_url

    async def receive(
        self,
        *,
        max_messages: int = 1,
        wait_time_seconds: int = 0,
    ) -> tuple[AsyncQueueMessage, ...]:
        validate_sqs_receive_options(
            max_messages=max_messages,
            wait_time_seconds=wait_time_seconds,
        )

        raw_response = await asyncio.to_thread(
            self._client.receive_message,
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_time_seconds,
            MessageSystemAttributeNames=["ApproximateReceiveCount"],
        )

        response = self._require_mapping(
            raw_response,
            operation="ReceiveMessage",
        )

        return self._parse_messages(response)

    async def acknowledge(
        self,
        message: AsyncQueueMessage,
    ) -> None:
        await asyncio.to_thread(
            self._client.delete_message,
            QueueUrl=self._queue_url,
            ReceiptHandle=message.receipt_handle,
        )

    async def health(self) -> dict[str, object]:
        """Return configuration health without contacting AWS."""

        return {
            "provider": self.provider_name,
            "network_checked": False,
            "queue_configured": True,
        }

    @classmethod
    def _parse_messages(
        cls,
        response: Mapping[str, object],
    ) -> tuple[AsyncQueueMessage, ...]:
        raw_messages = response.get("Messages")

        if raw_messages is None:
            return ()

        if not isinstance(
            raw_messages,
            list,
        ):
            raise ValueError("SQS ReceiveMessage response Messages must be a list.")

        messages: list[AsyncQueueMessage] = []

        for raw_message in raw_messages:
            if not isinstance(
                raw_message,
                Mapping,
            ):
                raise ValueError("SQS message must be a mapping.")

            message_id = cls._required_string(
                raw_message,
                "MessageId",
            )

            receipt_handle = cls._required_string(
                raw_message,
                "ReceiptHandle",
            )

            body = cls._required_string(
                raw_message,
                "Body",
            )

            receive_count = cls._receive_count(raw_message)

            messages.append(
                AsyncQueueMessage(
                    message_id=message_id,
                    receipt_handle=receipt_handle,
                    body=body,
                    receive_count=receive_count,
                )
            )

        return tuple(messages)

    @staticmethod
    def _receive_count(
        raw_message: Mapping[str, object],
    ) -> int:
        raw_attributes = raw_message.get("Attributes")

        if raw_attributes is None:
            return 1

        if not isinstance(
            raw_attributes,
            Mapping,
        ):
            raise ValueError("SQS message Attributes must be a mapping.")

        raw_count = raw_attributes.get("ApproximateReceiveCount")

        if raw_count is None:
            return 1

        if isinstance(raw_count, bool):
            raise ValueError("SQS ApproximateReceiveCount is invalid.")

        if isinstance(raw_count, int):
            receive_count = raw_count

        elif isinstance(raw_count, str):
            normalized = raw_count.strip()

            if not normalized.isdigit():
                raise ValueError("SQS ApproximateReceiveCount is invalid.")

            receive_count = int(normalized)

        else:
            raise ValueError("SQS ApproximateReceiveCount is invalid.")

        if receive_count <= 0:
            raise ValueError("SQS ApproximateReceiveCount must be greater than zero.")

        return receive_count

    @staticmethod
    def _required_string(
        message: Mapping[str, object],
        field_name: str,
    ) -> str:
        raw_value = message.get(field_name)

        if not isinstance(
            raw_value,
            str,
        ):
            raise ValueError(f"SQS message {field_name} must be a string.")

        normalized = raw_value.strip()

        if not normalized:
            raise ValueError(f"SQS message {field_name} must not be blank.")

        return normalized

    @staticmethod
    def _require_mapping(
        response: object,
        *,
        operation: str,
    ) -> Mapping[str, object]:
        if not isinstance(
            response,
            Mapping,
        ):
            raise ValueError(f"SQS {operation} returned an invalid response.")

        return response


def validate_sqs_receive_options(
    *,
    max_messages: int,
    wait_time_seconds: int,
) -> None:
    if not 1 <= max_messages <= 10:
        raise ValueError("max_messages must be between 1 and 10.")

    if not 0 <= wait_time_seconds <= 20:
        raise ValueError("wait_time_seconds must be between 0 and 20.")


def build_aws_async_queue(
    *,
    settings: Settings,
    gateway: AWSIntelligenceGateway,
) -> AsyncQueue:
    """Build the CaseMesh SQS abstraction according to AWS client mode."""

    if not settings.aws_async_processing_enabled:
        raise ValueError("AWS async queue requires aws_async_processing_enabled=true.")

    if settings.aws_client_mode == "mock":
        return MockSQSAsyncQueue()

    client = cast(
        SQSClientProtocol,
        gateway.sqs_client(),
    )

    return SQSAsyncQueue(
        client=client,
        queue_url=settings.aws_textract_queue_url,
    )
