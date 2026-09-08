import asyncio
import os
from uuid import UUID

from casemesh.mcp.client import CaseMeshMcpClient
from casemesh.services.mcp_retrieval import McpRetrievalService


DEFAULT_MCP_URL = (
    "https://casemesh-api-dev.lemonwater-0bb11448."
    "uaenorth.azurecontainerapps.io/mcp/"
)

DEFAULT_CASE_ID = "912ec51e-2a58-4a9c-9737-970327757211"

DEFAULT_QUERY = (
    "What database is used in this CaseMesh Azure environment?"
)


async def main() -> None:
    token = os.getenv(
        "MCP_AUTH_TOKEN",
        "",
    ).strip()

    if not token:
        raise RuntimeError(
            "MCP_AUTH_TOKEN is required."
        )

    url = os.getenv(
        "CASEMESH_MCP_HTTP_URL",
        DEFAULT_MCP_URL,
    )

    case_id = UUID(
        os.getenv(
            "CASEMESH_MCP_TEST_CASE_ID",
            DEFAULT_CASE_ID,
        )
    )

    query = os.getenv(
        "CASEMESH_MCP_TEST_QUERY",
        DEFAULT_QUERY,
    )

    client = CaseMeshMcpClient(
        url=url,
        token=token,
    )

    service = McpRetrievalService(
        client=client,
    )

    response = await service.search(
        case_id=case_id,
        query=query,
        top_k=3,
    )

    print("MCP RETRIEVAL ADAPTER PASS")
    print("MODE=", response.mode)
    print("EMBEDDING_MODEL=", response.embedding_model)
    print("RESULT_COUNT=", len(response.results))

    if not response.results:
        raise RuntimeError(
            "MCP retrieval adapter returned no evidence."
        )

    first = response.results[0]

    print(
        "TOP_VECTOR_SIMILARITY=",
        first.vector_similarity,
    )

    print(
        "TOP_CONTENT=",
        first.content,
    )


if __name__ == "__main__":
    asyncio.run(main())