import asyncio
import os
from uuid import UUID

from casemesh.mcp.client import CaseMeshMcpClient
from casemesh.services.mcp_cases import McpCaseReader

DEFAULT_MCP_URL = (
    "https://casemesh-api-dev.lemonwater-0bb11448."
    "uaenorth.azurecontainerapps.io/mcp/"
)

DEFAULT_CASE_ID = "912ec51e-2a58-4a9c-9737-970327757211"


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

    client = CaseMeshMcpClient(
        url=url,
        token=token,
    )

    reader = McpCaseReader(
        client=client,
    )

    case = await reader.get(case_id)

    if case is None:
        raise RuntimeError(
            "MCP case reader returned no case."
        )

    print("MCP CASE READER PASS")
    print("CASE_ID=", case.id)
    print("CASE_NUMBER=", case.case_number)
    print("TITLE=", case.title)
    print("STATUS=", case.status)
    print("PRIORITY=", case.priority)
    print("CUSTOMER_REF=", case.customer_ref)


if __name__ == "__main__":
    asyncio.run(main())