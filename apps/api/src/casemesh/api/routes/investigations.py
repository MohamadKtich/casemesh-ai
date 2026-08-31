from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.core.config import get_settings
from casemesh.db.session import get_db_session
from casemesh.embeddings.factory import get_embedding_provider
from casemesh.grounding.context import EvidenceContextBuilder
from casemesh.llm.factory import get_generation_provider
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.documents import DocumentRepository
from casemesh.repositories.investigations import InvestigationRepository
from casemesh.repositories.retrieval import RetrievalRepository
from casemesh.schemas.investigations import (
    InvestigationRunResponse,
    InvestigationStartRequest,
)
from casemesh.services.answers import AnswerService
from casemesh.services.investigations import InvestigationService
from casemesh.services.retrieval import RetrievalService

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_investigation_service(
    session: DbSession,
) -> InvestigationService:
    settings = get_settings()
    case_repository = CaseRepository(session)

    retrieval_service = RetrievalService(
        case_repository=case_repository,
        document_repository=DocumentRepository(session),
        retrieval_repository=RetrievalRepository(session),
        embedding_provider=get_embedding_provider(),
    )

    answer_service = AnswerService(
        retrieval_service=retrieval_service,
        generation_provider=get_generation_provider(),
        context_builder=EvidenceContextBuilder(
            max_context_chars=settings.answer_context_max_chars,
            max_source_chars=settings.answer_source_max_chars,
        ),
    )

    return InvestigationService(
        settings=settings,
        case_repository=case_repository,
        investigation_repository=InvestigationRepository(session),
        retrieval_service=retrieval_service,
        answer_service=answer_service,
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
