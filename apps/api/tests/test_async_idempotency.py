import pytest

from casemesh.intelligence.idempotency import (
    InMemoryCompletionIdempotencyStore,
)


@pytest.mark.asyncio
async def test_first_claim_is_acquired() -> None:
    store = InMemoryCompletionIdempotencyStore()

    assert await store.begin("aws-textract:job-1") == "acquired"


@pytest.mark.asyncio
async def test_second_inflight_claim_is_not_acquired() -> None:
    store = InMemoryCompletionIdempotencyStore()

    await store.begin("aws-textract:job-1")

    assert await store.begin("aws-textract:job-1") == "inflight"


@pytest.mark.asyncio
async def test_completed_claim_is_detected() -> None:
    store = InMemoryCompletionIdempotencyStore()

    key = "aws-textract:job-1"

    await store.begin(key)
    await store.complete(key)

    assert await store.begin(key) == "completed"


@pytest.mark.asyncio
async def test_release_allows_retry() -> None:
    store = InMemoryCompletionIdempotencyStore()

    key = "aws-textract:job-1"

    await store.begin(key)
    await store.release(key)

    assert await store.begin(key) == "acquired"


@pytest.mark.asyncio
async def test_release_does_not_remove_completed_key() -> None:
    store = InMemoryCompletionIdempotencyStore()

    key = "aws-textract:job-1"

    await store.begin(key)
    await store.complete(key)
    await store.release(key)

    assert await store.begin(key) == "completed"


@pytest.mark.asyncio
async def test_complete_requires_inflight_claim() -> None:
    store = InMemoryCompletionIdempotencyStore()

    with pytest.raises(
        ValueError,
        match="must be inflight",
    ):
        await store.complete("aws-textract:job-1")


@pytest.mark.asyncio
async def test_blank_key_is_rejected() -> None:
    store = InMemoryCompletionIdempotencyStore()

    with pytest.raises(
        ValueError,
        match="must not be blank",
    ):
        await store.begin(" ")


@pytest.mark.asyncio
async def test_health_exposes_non_durable_boundary() -> None:
    store = InMemoryCompletionIdempotencyStore()

    first = "aws-textract:job-1"
    second = "aws-textract:job-2"

    await store.begin(first)

    await store.begin(second)
    await store.complete(second)

    health = await store.health()

    assert health == {
        "provider": "memory-idempotency",
        "durable": False,
        "inflight_count": 1,
        "completed_count": 1,
    }
