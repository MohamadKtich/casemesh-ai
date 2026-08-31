from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.core.config import get_settings
from casemesh.db.session import get_db_session
from casemesh.embeddings.factory import get_embedding_provider
from casemesh.grounding.context import EvidenceContextBuilder
from casemesh.llm.factory import get_generation_provider
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.documents import DocumentRepository
from casemesh.repositories.retrieval import RetrievalRepository
from casemesh.schemas.answers import (
    GenerationHealthResponse,
    GroundedAnswerRequest,
    GroundedAnswerResponse,
)
from casemesh.services.answers import AnswerService
from casemesh.services.retrieval import RetrievalService

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_answer_service(session: DbSession) -> AnswerService:
    settings = get_settings()
    retrieval_service = RetrievalService(
        case_repository=CaseRepository(session),
        document_repository=DocumentRepository(session),
        retrieval_repository=RetrievalRepository(session),
        embedding_provider=get_embedding_provider(),
    )

    return AnswerService(
        retrieval_service=retrieval_service,
        generation_provider=get_generation_provider(),
        context_builder=EvidenceContextBuilder(
            max_context_chars=settings.answer_context_max_chars,
            max_source_chars=settings.answer_source_max_chars,
        ),
    )


AnswerServiceDep = Annotated[AnswerService, Depends(get_answer_service)]


@router.get(
    "/generation/health",
    response_model=GenerationHealthResponse,
    tags=["generation"],
)
async def generation_health(
    service: AnswerServiceDep,
) -> GenerationHealthResponse:
    payload = await service.generation_health()
    return GenerationHealthResponse.model_validate(payload)


@router.post(
    "/cases/{case_id}/answers",
    response_model=GroundedAnswerResponse,
    tags=["answers"],
)
async def answer_case_question(
    case_id: UUID,
    payload: GroundedAnswerRequest,
    service: AnswerServiceDep,
) -> GroundedAnswerResponse:
    return await service.answer(
        case_id=case_id,
        question=payload.question,
        top_k=payload.top_k,
    )
