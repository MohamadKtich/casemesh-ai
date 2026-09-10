from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class CaseMeshMcpClient:
    def __init__(
        self,
        *,
        url: str,
        token: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._url = url.strip()
        self._token = token.strip()
        self._timeout_seconds = timeout_seconds

        if not self._url:
            raise ValueError("MCP client URL must not be empty.")

        if not self._token:
            raise ValueError("MCP authentication token must not be empty.")

    async def get_case_status(
        self,
        *,
        case_id: str,
    ) -> dict[str, Any]:
        return await self._call_tool(
            "get_case_status",
            {
                "case_id": case_id,
            },
        )

    async def search_case_evidence(
        self,
        *,
        case_id: str,
        query: str,
        top_k: int,
    ) -> dict[str, Any]:
        return await self._call_tool(
            "search_case_evidence",
            {
                "case_id": case_id,
                "query": query,
                "top_k": top_k,
            },
        )

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict[str, object],
    ) -> dict[str, Any]:
        async with httpx2.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._token}",
            },
            follow_redirects=True,
            timeout=self._timeout_seconds,
        ) as http_client, streamable_http_client(
            self._url,
            http_client=http_client,
        ) as (
            read_stream,
            write_stream,
        ), ClientSession(
            read_stream,
            write_stream,
        ) as session:
            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments=arguments,
            )

            if result.is_error:
                message = "MCP tool call failed."

                if result.content:
                    first = result.content[0]
                    text = getattr(first, "text", None)

                    if text:
                        message = str(text)

                raise RuntimeError(
                    f"{tool_name}: {message}"
                )

            structured = result.structured_content

            if not isinstance(structured, dict):
                raise RuntimeError(
                    f"{tool_name} returned no structured content."
                )

            return structured