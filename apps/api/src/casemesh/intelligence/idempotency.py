import asyncio
from typing import Literal, Protocol

CompletionClaimDecision = Literal[
    "acquired",
    "completed",
    "inflight",
]

CompletionProcessingState = Literal[
    "inflight",
    "completed",
]


class CompletionIdempotencyStore(Protocol):
    """Coordinate duplicate asynchronous completion deliveries."""

    async def begin(
        self,
        key: str,
    ) -> CompletionClaimDecision:
        """Attempt to claim one completion event for processing."""

    async def complete(
        self,
        key: str,
    ) -> None:
        """Mark a previously acquired completion as finished."""

    async def release(
        self,
        key: str,
    ) -> None:
        """Release an inflight claim after processing failure."""

    async def health(
        self,
    ) -> dict[str, object]:
        """Return local idempotency-store health information."""


class InMemoryCompletionIdempotencyStore:
    """Process-local idempotency store for deterministic tests and development.

    This implementation is intentionally not durable across process restarts.
    Production persistence can implement the same CompletionIdempotencyStore
    protocol without changing the completion consumer.
    """

    provider_name = "memory-idempotency"

    def __init__(self) -> None:
        self._states: dict[
            str,
            CompletionProcessingState,
        ] = {}

        self._lock = asyncio.Lock()

    async def begin(
        self,
        key: str,
    ) -> CompletionClaimDecision:
        normalized_key = self._normalize_key(key)

        async with self._lock:
            state = self._states.get(normalized_key)

            if state == "completed":
                return "completed"

            if state == "inflight":
                return "inflight"

            self._states[normalized_key] = "inflight"

            return "acquired"

    async def complete(
        self,
        key: str,
    ) -> None:
        normalized_key = self._normalize_key(key)

        async with self._lock:
            state = self._states.get(normalized_key)

            if state != "inflight":
                raise ValueError("Idempotency key must be inflight before completion.")

            self._states[normalized_key] = "completed"

    async def release(
        self,
        key: str,
    ) -> None:
        normalized_key = self._normalize_key(key)

        async with self._lock:
            if self._states.get(normalized_key) == "inflight":
                del self._states[normalized_key]

    async def health(
        self,
    ) -> dict[str, object]:
        async with self._lock:
            inflight_count = sum(1 for state in self._states.values() if state == "inflight")

            completed_count = sum(1 for state in self._states.values() if state == "completed")

        return {
            "provider": self.provider_name,
            "durable": False,
            "inflight_count": inflight_count,
            "completed_count": completed_count,
        }

    @staticmethod
    def _normalize_key(
        key: str,
    ) -> str:
        normalized_key = key.strip()

        if not normalized_key:
            raise ValueError("Idempotency key must not be blank.")

        return normalized_key
