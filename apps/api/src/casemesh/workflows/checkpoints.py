import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from casemesh.core.config import Settings


def to_psycopg_url(database_url: str) -> str:
    """
    Convert the SQLAlchemy asyncpg database URL into a psycopg-compatible URL.

    SQLAlchemy uses:
        postgresql+asyncpg://...

    psycopg expects:
        postgresql://...

    Azure PostgreSQL may also provide:
        ssl=require

    while psycopg expects:
        sslmode=require
    """
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://",
            "postgresql://",
            1,
        )

    parts = urlsplit(database_url)

    query_items = parse_qsl(parts.query, keep_blank_values=True)
    has_sslmode = any(key.lower() == "sslmode" for key, _ in query_items)

    converted_query: list[tuple[str, str]] = []

    for key, value in query_items:
        if key.lower() == "ssl":
            if not has_sslmode:
                converted_query.append(("sslmode", value))
            continue

        converted_query.append((key, value))

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(converted_query),
            parts.fragment,
        )
    )


def _enable_strict_msgpack() -> None:
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")


@asynccontextmanager
async def open_checkpointer(
    settings: Settings,
) -> AsyncIterator[AsyncPostgresSaver]:
    _enable_strict_msgpack()

    connection_string = to_psycopg_url(settings.database_url)

    async with AsyncPostgresSaver.from_conn_string(
        connection_string
    ) as checkpointer:
        yield checkpointer


async def setup_checkpointer(settings: Settings) -> None:
    async with open_checkpointer(settings) as checkpointer:
        await checkpointer.setup()