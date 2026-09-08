import asyncio
import os

import httpx2

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp/"
DEFAULT_TIMEOUT_SECONDS = 120.0


def get_mcp_url() -> str:
    return (
        os.getenv("CASEMESH_MCP_HTTP_URL")
        or os.getenv("MCP_CLIENT_URL")
        or DEFAULT_MCP_URL
    ).strip()


def get_timeout_seconds() -> float:
    raw_value = (
        os.getenv("CASEMESH_MCP_HTTP_TIMEOUT_SECONDS")
        or os.getenv("MCP_CLIENT_TIMEOUT_SECONDS")
        or str(DEFAULT_TIMEOUT_SECONDS)
    ).strip()

    try:
        timeout_seconds = float(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            "MCP client timeout must be a valid number."
        ) from exc

    if timeout_seconds <= 0:
        raise RuntimeError(
            "MCP client timeout must be greater than zero."
        )

    return timeout_seconds


async def main() -> None:
    url = get_mcp_url()

    token = os.getenv(
        "MCP_AUTH_TOKEN",
        "",
    ).strip()

    if not token:
        raise RuntimeError(
            "MCP_AUTH_TOKEN is required for the HTTP MCP test."
        )

    timeout_seconds = get_timeout_seconds()

    print("MCP URL=", url)
    print("MCP TIMEOUT SECONDS=", timeout_seconds)

    async with httpx2.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
        },
        follow_redirects=True,
        timeout=timeout_seconds,
    ) as http_client:
        async with streamable_http_client(
            url,
            http_client=http_client,
        ) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:
                initialize_result = await session.initialize()

                print("MCP HTTP INITIALIZE PASS")
                print(
                    "SERVER=",
                    initialize_result.server_info.name,
                )

                tools_result = await session.list_tools()

                print(
                    "TOOLS=",
                    [
                        tool.name
                        for tool in tools_result.tools
                    ],
                )

                print("MCP HTTP AUTH PASS")


if __name__ == "__main__":
    asyncio.run(main())