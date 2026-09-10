from unittest.mock import AsyncMock

import pytest

from casemesh.mcp.client import CaseMeshMcpClient


def test_client_rejects_empty_url() -> None:
    with pytest.raises(
        ValueError,
        match="MCP client URL must not be empty",
    ):
        CaseMeshMcpClient(
            url="",
            token="secret-token",
        )


def test_client_rejects_whitespace_url() -> None:
    with pytest.raises(
        ValueError,
        match="MCP client URL must not be empty",
    ):
        CaseMeshMcpClient(
            url="   ",
            token="secret-token",
        )


def test_client_rejects_empty_token() -> None:
    with pytest.raises(
        ValueError,
        match="MCP authentication token must not be empty",
    ):
        CaseMeshMcpClient(
            url="http://127.0.0.1:8000/mcp/",
            token="",
        )


def test_client_rejects_whitespace_token() -> None:
    with pytest.raises(
        ValueError,
        match="MCP authentication token must not be empty",
    ):
        CaseMeshMcpClient(
            url="http://127.0.0.1:8000/mcp/",
            token="   ",
        )


def test_client_normalizes_url_and_token() -> None:
    client = CaseMeshMcpClient(
        url="  http://127.0.0.1:8000/mcp/  ",
        token="  secret-token  ",
        timeout_seconds=30.0,
    )

    assert client._url == (
        "http://127.0.0.1:8000/mcp/"
    )
    assert client._token == "secret-token"
    assert client._timeout_seconds == 30.0


@pytest.mark.asyncio
async def test_get_case_status_delegates_to_mcp_tool() -> None:
    client = CaseMeshMcpClient(
        url="http://127.0.0.1:8000/mcp/",
        token="secret-token",
    )

    expected = {
        "case_number": "CASE-001",
        "status": "open",
    }

    mock_call = AsyncMock(
        return_value=expected,
    )

    client._call_tool = mock_call

    result = await client.get_case_status(
        case_id="case-id-123",
    )

    assert result == expected

    mock_call.assert_awaited_once_with(
        "get_case_status",
        {
            "case_id": "case-id-123",
        },
    )


@pytest.mark.asyncio
async def test_search_case_evidence_delegates_to_mcp_tool() -> None:
    client = CaseMeshMcpClient(
        url="http://127.0.0.1:8000/mcp/",
        token="secret-token",
    )

    expected = {
        "found": True,
        "result_count": 2,
    }

    mock_call = AsyncMock(
        return_value=expected,
    )

    client._call_tool = mock_call

    result = await client.search_case_evidence(
        case_id="case-id-123",
        query="database",
        top_k=3,
    )

    assert result == expected

    mock_call.assert_awaited_once_with(
        "search_case_evidence",
        {
            "case_id": "case-id-123",
            "query": "database",
            "top_k": 3,
        },
    )
