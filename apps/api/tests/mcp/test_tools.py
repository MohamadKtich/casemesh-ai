from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

import casemesh.mcp.tools.cases as case_tools
import casemesh.mcp.tools.evidence as evidence_tools

CASE_ID = "912ec51e-2a58-4a9c-9737-970327757211"


class FakeServer:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):
        def decorator(function):
            self.tools[function.__name__] = function
            return function

        return decorator


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> bool:
        return False


def fake_session_local() -> FakeSessionContext:
    return FakeSessionContext()


def get_registered_tool(
    server: FakeServer,
    name: str,
):
    return server.tools[name]


@pytest.mark.asyncio
async def test_get_case_status_rejects_invalid_uuid() -> None:
    server = FakeServer()

    case_tools.register_case_tools(server)

    tool = get_registered_tool(
        server,
        "get_case_status",
    )

    result = await tool(
        case_id="not-a-valid-uuid",
    )

    assert result == {
        "found": False,
        "error": "invalid_case_id",
        "message": "case_id must be a valid UUID.",
    }


@pytest.mark.asyncio
async def test_get_case_status_returns_not_found(
    monkeypatch,
) -> None:
    class FakeCaseRepository:
        def __init__(self, session) -> None:
            self.session = session

        async def get(self, case_id):
            return None

    monkeypatch.setattr(
        case_tools,
        "AsyncSessionLocal",
        fake_session_local,
    )

    monkeypatch.setattr(
        case_tools,
        "CaseRepository",
        FakeCaseRepository,
    )

    server = FakeServer()
    case_tools.register_case_tools(server)

    tool = get_registered_tool(
        server,
        "get_case_status",
    )

    result = await tool(
        case_id=CASE_ID,
    )

    assert result == {
        "found": False,
        "case_id": CASE_ID,
        "error": "case_not_found",
        "message": (
            "No CaseMesh case exists with this case_id."
        ),
    }


@pytest.mark.asyncio
async def test_get_case_status_returns_case(
    monkeypatch,
) -> None:
    case = SimpleNamespace(
        id=UUID(CASE_ID),
        case_number="CASE-001",
        title="Azure database investigation",
        status="open",
        priority="high",
        customer_ref="CUSTOMER-001",
        updated_at=datetime(
            2026,
            9,
            10,
            8,
            0,
            tzinfo=UTC,
        ),
    )

    class FakeCaseRepository:
        def __init__(self, session) -> None:
            self.session = session

        async def get(self, case_id):
            assert case_id == UUID(CASE_ID)
            return case

    monkeypatch.setattr(
        case_tools,
        "AsyncSessionLocal",
        fake_session_local,
    )

    monkeypatch.setattr(
        case_tools,
        "CaseRepository",
        FakeCaseRepository,
    )

    server = FakeServer()
    case_tools.register_case_tools(server)

    tool = get_registered_tool(
        server,
        "get_case_status",
    )

    result = await tool(
        case_id=CASE_ID,
    )

    assert result == {
        "found": True,
        "case_id": CASE_ID,
        "case_number": "CASE-001",
        "title": "Azure database investigation",
        "status": "open",
        "priority": "high",
        "customer_ref": "CUSTOMER-001",
        "updated_at": "2026-09-10T08:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_search_case_evidence_rejects_invalid_uuid() -> None:
    server = FakeServer()

    evidence_tools.register_evidence_tools(server)

    tool = get_registered_tool(
        server,
        "search_case_evidence",
    )

    result = await tool(
        case_id="invalid",
        query="database",
        top_k=3,
    )

    assert result == {
        "found": False,
        "error": "invalid_case_id",
        "message": "case_id must be a valid UUID.",
    }


@pytest.mark.asyncio
async def test_search_case_evidence_rejects_empty_query() -> None:
    server = FakeServer()

    evidence_tools.register_evidence_tools(server)

    tool = get_registered_tool(
        server,
        "search_case_evidence",
    )

    result = await tool(
        case_id=CASE_ID,
        query="   ",
        top_k=3,
    )

    assert result == {
        "found": False,
        "error": "empty_query",
        "message": "query must not be empty.",
    }


@pytest.mark.parametrize(
    "top_k",
    [
        0,
        11,
    ],
)
@pytest.mark.asyncio
async def test_search_case_evidence_rejects_invalid_top_k(
    top_k: int,
) -> None:
    server = FakeServer()

    evidence_tools.register_evidence_tools(server)

    tool = get_registered_tool(
        server,
        "search_case_evidence",
    )

    result = await tool(
        case_id=CASE_ID,
        query="database",
        top_k=top_k,
    )

    assert result == {
        "found": False,
        "error": "invalid_top_k",
        "message": "top_k must be between 1 and 10.",
    }


def configure_evidence_dependencies(
    monkeypatch,
    *,
    outcome,
) -> list[dict]:
    calls: list[dict] = []

    class FakeRepository:
        def __init__(self, session) -> None:
            self.session = session

    class FakeRetrievalService:
        def __init__(
            self,
            *,
            case_repository,
            document_repository,
            retrieval_repository,
            embedding_provider,
        ) -> None:
            self.case_repository = case_repository
            self.document_repository = document_repository
            self.retrieval_repository = retrieval_repository
            self.embedding_provider = embedding_provider

        async def search(
            self,
            *,
            case_id,
            query,
            top_k,
        ):
            calls.append(
                {
                    "case_id": case_id,
                    "query": query,
                    "top_k": top_k,
                }
            )

            if isinstance(
                outcome,
                BaseException,
            ):
                raise outcome

            return outcome

    monkeypatch.setattr(
        evidence_tools,
        "AsyncSessionLocal",
        fake_session_local,
    )

    monkeypatch.setattr(
        evidence_tools,
        "CaseRepository",
        FakeRepository,
    )

    monkeypatch.setattr(
        evidence_tools,
        "DocumentRepository",
        FakeRepository,
    )

    monkeypatch.setattr(
        evidence_tools,
        "RetrievalRepository",
        FakeRepository,
    )

    monkeypatch.setattr(
        evidence_tools,
        "get_embedding_provider",
        lambda: object(),
    )

    monkeypatch.setattr(
        evidence_tools,
        "RetrievalService",
        FakeRetrievalService,
    )

    return calls


@pytest.mark.asyncio
async def test_search_case_evidence_handles_http_exception(
    monkeypatch,
) -> None:
    configure_evidence_dependencies(
        monkeypatch,
        outcome=HTTPException(
            status_code=404,
            detail="Case not found.",
        ),
    )

    server = FakeServer()
    evidence_tools.register_evidence_tools(server)

    tool = get_registered_tool(
        server,
        "search_case_evidence",
    )

    result = await tool(
        case_id=CASE_ID,
        query="database",
        top_k=3,
    )

    assert result == {
        "found": False,
        "error": "retrieval_error",
        "status_code": 404,
        "message": "Case not found.",
    }


@pytest.mark.asyncio
async def test_search_case_evidence_handles_provider_error(
    monkeypatch,
) -> None:
    configure_evidence_dependencies(
        monkeypatch,
        outcome=RuntimeError(
            "Embedding provider unavailable."
        ),
    )

    server = FakeServer()
    evidence_tools.register_evidence_tools(server)

    tool = get_registered_tool(
        server,
        "search_case_evidence",
    )

    result = await tool(
        case_id=CASE_ID,
        query="database",
        top_k=3,
    )

    assert result == {
        "found": False,
        "error": "provider_error",
        "message": "Embedding provider unavailable.",
    }


@pytest.mark.asyncio
async def test_search_case_evidence_returns_results(
    monkeypatch,
) -> None:
    chunk_id = UUID(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )

    document_id = UUID(
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    )

    response = SimpleNamespace(
        query="database",
        top_k=3,
        embedding_model="nomic-embed-text",
        results=[
            SimpleNamespace(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=2,
                content=(
                    "The environment uses PostgreSQL."
                ),
                metadata_json={
                    "source": "case-document",
                },
                hybrid_score=0.95,
                vector_rank=1,
                keyword_rank=2,
                vector_similarity=0.91,
                keyword_score=0.82,
            )
        ],
    )

    calls = configure_evidence_dependencies(
        monkeypatch,
        outcome=response,
    )

    server = FakeServer()
    evidence_tools.register_evidence_tools(server)

    tool = get_registered_tool(
        server,
        "search_case_evidence",
    )

    result = await tool(
        case_id=CASE_ID,
        query="  database  ",
        top_k=3,
    )

    assert calls == [
        {
            "case_id": UUID(CASE_ID),
            "query": "database",
            "top_k": 3,
        }
    ]

    assert result == {
        "found": True,
        "case_id": CASE_ID,
        "query": "database",
        "top_k": 3,
        "mode": "hybrid_rrf",
        "embedding_model": "nomic-embed-text",
        "result_count": 1,
        "results": [
            {
                "chunk_id": str(chunk_id),
                "document_id": str(document_id),
                "chunk_index": 2,
                "content": (
                    "The environment uses PostgreSQL."
                ),
                "metadata": {
                    "source": "case-document",
                },
                "hybrid_score": 0.95,
                "vector_rank": 1,
                "keyword_rank": 2,
                "vector_similarity": 0.91,
                "keyword_score": 0.82,
            }
        ],
    }
