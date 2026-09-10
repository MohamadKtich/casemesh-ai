import asyncio
import json
import os
import sys

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

DEFAULT_CASE_ID = "912ec51e-2a58-4a9c-9737-970327757211"

DEFAULT_QUERY = (
    "What database is used in this CaseMesh Azure environment?"
)


def build_server_environment() -> dict[str, str]:
    names = (
        "DATABASE_URL",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "EMBEDDING_DIMENSION",
        "OLLAMA_BASE_URL",
        "HF_TOKEN",
        "HF_INFERENCE_BASE_URL",
    )

    environment: dict[str, str] = {}

    for name in names:
        value = os.getenv(name)

        if value:
            environment[name] = value

    if "DATABASE_URL" not in environment:
        raise RuntimeError(
            "DATABASE_URL is required for the MCP evidence test."
        )

    return environment


async def main() -> None:
    case_id = os.getenv(
        "CASEMESH_MCP_TEST_CASE_ID",
        DEFAULT_CASE_ID,
    )

    query = os.getenv(
        "CASEMESH_MCP_TEST_QUERY",
        DEFAULT_QUERY,
    )

    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "casemesh.mcp.stdio",
        ],
        env=build_server_environment(),
    )

    async with stdio_client(
        server_parameters
    ) as (
        read_stream,
        write_stream,
    ), ClientSession(
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
            "search_case_evidence",
            arguments={
                "case_id": case_id,
                "query": query,
                "top_k": 3,
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
                "MCP search_case_evidence returned an error."
            )

        structured = result.structured_content

        if not structured:
            raise RuntimeError(
                "MCP evidence search returned no structured content."
            )

        if not structured.get("found"):
            raise RuntimeError(
                "MCP evidence search returned no evidence."
            )

        print("MCP EVIDENCE SEARCH PASS")
        print(
            "MODE=",
            structured.get("mode"),
        )
        print(
            "EMBEDDING_MODEL=",
            structured.get("embedding_model"),
        )
        print(
            "RESULT_COUNT=",
            structured.get("result_count"),
        )

        results = structured.get("results")

        if isinstance(results, list) and results:
            first = results[0]

            if isinstance(first, dict):
                print(
                    "TOP_VECTOR_SIMILARITY=",
                    first.get("vector_similarity"),
                )
                print(
                    "TOP_CONTENT=",
                    first.get("content"),
                )


if __name__ == "__main__":
    asyncio.run(main())