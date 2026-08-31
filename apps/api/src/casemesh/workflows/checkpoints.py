import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from casemesh.core.config import Settings


def to_psycopg_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace(
            "postgresql+asyncpg://",
            "postgresql://",
            1,
        )
    return database_url


def _enable_strict_msgpack() -> None:
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")


@asynccontextmanager
async def open_checkpointer(
    settings: Settings,
) -> AsyncIterator[AsyncPostgresSaver]:
    _enable_strict_msgpack()
    connection_string = to_psycopg_url(settings.database_url)

    async with AsyncPostgresSaver.from_conn_string(connection_string) as checkpointer:
        yield checkpointer


async def setup_checkpointer(settings: Settings) -> None:
    async with open_checkpointer(settings) as checkpointer:
        await checkpointer.setup()
