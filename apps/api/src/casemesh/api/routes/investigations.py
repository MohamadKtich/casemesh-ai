from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.core.config import Settings, get_settings
from casemesh.db.session import get_db_session
from casemesh.embeddings.factory import get_embedding_provider
from casemesh.grounding.context import EvidenceContextBuilder
from casemesh.integrations.aws import (
    build_aws_intelligence_gateway,
)
from casemesh.integrations.aws.bedrock_guardrails import (
    build_bedrock_safety_guardrail_provider,
)
from casemesh.integrations.aws.bedrock_review import (
    build_bedrock_second_review_provider,
)
from casemesh.intelligence.contracts import (
    SecondReviewProvider,
)
from casemesh.intelligence.guarded_review import (
    GuardedSecondReviewProvider,
)
from casemesh.llm.factory import get_generation_provider
from casemesh.mcp.client import CaseMeshMcpClient
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.documents import DocumentRepository
from casemesh.repositories.investigations import InvestigationRepository
from casemesh.repositories.retrieval import RetrievalRepository
from casemesh.schemas.investigations import (
    InvestigationRunResponse,
    InvestigationStartRequest,
)
from casemesh.services.answers import AnswerService
from casemesh.services.case_reader import (
    CaseReader,
    RepositoryCaseReader,
)
from casemesh.services.investigations import InvestigationService
from casemesh.services.mcp_cases import McpCaseReader
from casemesh.services.mcp_retrieval import McpRetrievalService
from casemesh.services.retrieval import RetrievalService
from casemesh.services.retrieval_contract import RetrievalSearcher

router = APIRouter()

DbSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


def _build_mcp_client(
    *,
    settings: Settings,
) -> CaseMeshMcpClient:
    if not settings.mcp_auth_token.strip():
        raise RuntimeError("INVESTIGATION_USE_MCP is enabled but MCP_AUTH_TOKEN is not configured.")

    return CaseMeshMcpClient(
        url=settings.mcp_client_url,
        token=settings.mcp_auth_token,
        timeout_seconds=(settings.mcp_client_timeout_seconds),
    )


def build_case_reader(
    *,
    session: AsyncSession,
) -> CaseReader:
    settings = get_settings()

    if settings.investigation_use_mcp:
        return McpCaseReader(
            client=_build_mcp_client(
                settings=settings,
            ),
        )

    return RepositoryCaseReader(
        repository=CaseRepository(session),
    )


def build_retrieval_searcher(
    *,
    session: AsyncSession,
) -> RetrievalSearcher:
    settings = get_settings()

    if settings.investigation_use_mcp:
        return McpRetrievalService(
            client=_build_mcp_client(
                settings=settings,
            ),
        )

    return RetrievalService(
        case_repository=CaseRepository(session),
        document_repository=DocumentRepository(session),
        retrieval_repository=RetrievalRepository(session),
        embedding_provider=get_embedding_provider(),
    )


def build_second_review_provider(
    *,
    settings: Settings,
) -> SecondReviewProvider | None:
    """Build optional second review with independent safety guardrails."""

    if not settings.aws_bedrock_review_enabled:
        return None

    gateway = build_aws_intelligence_gateway(settings)

    reviewer = build_bedrock_second_review_provider(
        settings=settings,
        gateway=gateway,
    )

    if not settings.aws_bedrock_guardrails_enabled:
        return reviewer

    guardrail = build_bedrock_safety_guardrail_provider(
        settings=settings,
        gateway=gateway,
    )

    return GuardedSecondReviewProvider(
        reviewer=reviewer,
        guardrail=guardrail,
    )


def get_investigation_service(
    session: DbSession,
) -> InvestigationService:
    settings = get_settings()

    case_reader = build_case_reader(
        session=session,
    )

    retrieval_searcher = build_retrieval_searcher(
        session=session,
    )

    answer_service = AnswerService(
        retrieval_service=retrieval_searcher,
        generation_provider=get_generation_provider(),
        context_builder=EvidenceContextBuilder(
            max_context_chars=(settings.answer_context_max_chars),
            max_source_chars=(settings.answer_source_max_chars),
        ),
    )

    return InvestigationService(
        settings=settings,
        case_reader=case_reader,
        investigation_repository=InvestigationRepository(session),
        retrieval_service=retrieval_searcher,
        answer_service=answer_service,
        second_review_provider=(
            build_second_review_provider(
                settings=settings,
            )
        ),
    )


InvestigationServiceDep = Annotated[
    InvestigationService,
    Depends(get_investigation_service),
]


@router.post(
    "/cases/{case_id}/investigations",
    response_model=InvestigationRunResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["investigations"],
)
async def start_investigation(
    case_id: UUID,
    payload: InvestigationStartRequest,
    service: InvestigationServiceDep,
) -> InvestigationRunResponse:
    return await service.start(
        case_id=case_id,
        objective=payload.objective,
        manual_second_review_requested=(payload.manual_second_review_requested),
    )


@router.get(
    "/cases/{case_id}/investigations",
    response_model=list[InvestigationRunResponse],
    tags=["investigations"],
)
async def list_investigations(
    case_id: UUID,
    service: InvestigationServiceDep,
) -> list[InvestigationRunResponse]:
    return await service.list(case_id=case_id)


@router.get(
    "/cases/{case_id}/investigations/{workflow_id}",
    response_model=InvestigationRunResponse,
    tags=["investigations"],
)
async def get_investigation(
    case_id: UUID,
    workflow_id: UUID,
    service: InvestigationServiceDep,
) -> InvestigationRunResponse:
    return await service.get(
        case_id=case_id,
        workflow_id=workflow_id,
    )
