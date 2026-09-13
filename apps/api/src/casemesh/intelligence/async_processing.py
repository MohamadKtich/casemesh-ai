from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AsyncQueueMessage:
    """Normalized message received from an asynchronous work queue."""

    message_id: str
    receipt_handle: str
    body: str
    receive_count: int = 1

    def __post_init__(self) -> None:
        if not self.message_id.strip():
            raise ValueError("Async queue message_id must not be blank.")

        if not self.receipt_handle.strip():
            raise ValueError("Async queue receipt_handle must not be blank.")

        if not self.body.strip():
            raise ValueError("Async queue message body must not be blank.")

        if self.receive_count <= 0:
            raise ValueError("Async queue receive_count must be greater than zero.")


class AsyncQueue(Protocol):
    """Minimal async queue abstraction used by CaseMesh."""

    @property
    def provider_name(self) -> str:
        """Return the queue provider identifier."""

    async def receive(
        self,
        *,
        max_messages: int = 1,
        wait_time_seconds: int = 0,
    ) -> tuple[AsyncQueueMessage, ...]:
        """Receive zero or more messages without acknowledging them."""

    async def acknowledge(
        self,
        message: AsyncQueueMessage,
    ) -> None:
        """Acknowledge successful processing of a message."""

    async def health(self) -> dict[str, object]:
        """Return local queue health information."""
