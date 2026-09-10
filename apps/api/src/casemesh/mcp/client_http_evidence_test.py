import asyncio
import json
import os

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_MCP_URL = (
    "https://casemesh-api-dev.lemonwater-0bb11448."
    "uaenorth.azurecontainerapps.io/mcp/"
)

DEFAULT_CASE_ID = "912ec51e-2a58-4a9c-9737-970327757211"

DEFAULT_QUERY = (
    "What database is used in this CaseMesh Azure environment?"
)


async def main() -> None:
    url = os.getenv(
        "CASEMESH_MCP_HTTP_URL",
        DEFAULT_MCP_URL,
    )

    token = os.getenv(
        "MCP_AUTH_TOKEN",
        "",
    ).strip()

    case_id = os.getenv(
        "CASEMESH_MCP_TEST_CASE_ID",
        DEFAULT_CASE_ID,
    )

    query = os.getenv(
        "CASEMESH_MCP_TEST_QUERY",
        DEFAULT_QUERY,
    )

    if not token:
        raise RuntimeError(
            "MCP_AUTH_TOKEN is required."
        )

    async with httpx2.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
        },
        follow_redirects=True,
    ) as http_client, streamable_http_client(
        url,
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

        print("REMOTE MCP CALL RESULT=")
        print(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )
        )

        if result.is_error:
            raise RuntimeError(
                "Remote MCP evidence search failed."
            )

        structured = result.structured_content

        if not structured:
            raise RuntimeError(
                "Remote MCP returned no structured content."
            )

        if not structured.get("found"):
            raise RuntimeError(
                "Remote MCP returned no evidence."
            )

        print("REMOTE MCP EVIDENCE PASS")
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