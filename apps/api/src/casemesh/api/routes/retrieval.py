from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.db.session import get_db_session
from casemesh.embeddings.factory import get_embedding_provider
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.documents import DocumentRepository
from casemesh.repositories.retrieval import RetrievalRepository
from casemesh.schemas.retrieval import (
    DocumentEmbeddingResponse,
    EmbeddingHealthResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from casemesh.services.retrieval import RetrievalService

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_retrieval_service(session: DbSession) -> RetrievalService:
    return RetrievalService(
        case_repository=CaseRepository(session),
        document_repository=DocumentRepository(session),
        retrieval_repository=RetrievalRepository(session),
        embedding_provider=get_embedding_provider(),
    )


RetrievalServiceDep = Annotated[
    RetrievalService,
    Depends(get_retrieval_service),
]


@router.get(
    "/embeddings/health",
    response_model=EmbeddingHealthResponse,
    tags=["embeddings"],
)
async def embedding_health(
    service: RetrievalServiceDep,
) -> EmbeddingHealthResponse:
    payload = await service.embedding_health()
    return EmbeddingHealthResponse.model_validate(payload)


@router.post(
    "/cases/{case_id}/documents/{document_id}/embed",
    response_model=DocumentEmbeddingResponse,
    tags=["embeddings"],
)
async def embed_document(
    case_id: UUID,
    document_id: UUID,
    service: RetrievalServiceDep,
) -> DocumentEmbeddingResponse:
    return await service.embed_document(
        case_id=case_id,
        document_id=document_id,
    )


@router.post(
    "/cases/{case_id}/retrieval/search",
    response_model=RetrievalSearchResponse,
    tags=["retrieval"],
)
async def search_case_evidence(
    case_id: UUID,
    payload: RetrievalSearchRequest,
    service: RetrievalServiceDep,
) -> RetrievalSearchResponse:
    return await service.search(
        case_id=case_id,
        query=payload.query,
        top_k=payload.top_k,
    )
