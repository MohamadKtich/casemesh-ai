import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


DEFAULT_CASE_ID = "912ec51e-2a58-4a9c-9737-970327757211"


async def main() -> None:
    case_id = os.getenv(
        "CASEMESH_MCP_TEST_CASE_ID",
        DEFAULT_CASE_ID,
    )

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required for the MCP integration test."
        )

    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "casemesh.mcp.stdio",
        ],
        env={
            "DATABASE_URL": database_url,
        },
    )

    async with stdio_client(
        server_parameters
    ) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:
            await session.initialize()

            tools_result = await session.list_tools()

            print(
                "TOOLS=",
                [tool.name for tool in tools_result.tools],
            )

            result = await session.call_tool(
                "get_case_status",
                arguments={
                    "case_id": case_id,
                },
            )

            payload = result.model_dump(
                mode="json",
                by_alias=True,
            )

            print("CALL RESULT=")
            print(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                )
            )

            if result.is_error:
                raise RuntimeError(
                    "MCP get_case_status returned an error."
                )

            structured = result.structured_content

            if not structured:
                raise RuntimeError(
                    "MCP get_case_status returned no structured content."
                )

            print("MCP ROUND-TRIP PASS")
            print(
                "CASE_NUMBER=",
                structured.get("case_number"),
            )
            print(
                "STATUS=",
                structured.get("status"),
            )
            print(
                "PRIORITY=",
                structured.get("priority"),
            )


if __name__ == "__main__":
    asyncio.run(main())