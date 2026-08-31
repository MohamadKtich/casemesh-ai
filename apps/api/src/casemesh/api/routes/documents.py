from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.db.session import get_db_session
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.documents import DocumentRepository
from casemesh.schemas.documents import DocumentChunkRead, DocumentRead
from casemesh.services.documents import DocumentService

router = APIRouter(prefix="/cases/{case_id}/documents", tags=["documents"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_document_service(session: DbSession) -> DocumentService:
    return DocumentService(
        CaseRepository(session),
        DocumentRepository(session),
    )


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
UploadedFile = Annotated[UploadFile, File(description="Case evidence document")]


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    case_id: UUID,
    file: UploadedFile,
    service: DocumentServiceDep,
) -> DocumentRead:
    document = await service.upload(case_id, file)
    return DocumentRead.model_validate(document)


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    case_id: UUID,
    service: DocumentServiceDep,
) -> list[DocumentRead]:
    documents = await service.list_for_case(case_id)
    return [DocumentRead.model_validate(document) for document in documents]


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    case_id: UUID,
    document_id: UUID,
    service: DocumentServiceDep,
) -> DocumentRead:
    document = await service.get(case_id, document_id)
    return DocumentRead.model_validate(document)


@router.post("/{document_id}/ingest", response_model=DocumentRead)
async def ingest_document(
    case_id: UUID,
    document_id: UUID,
    service: DocumentServiceDep,
) -> DocumentRead:
    document = await service.ingest(case_id, document_id)
    return DocumentRead.model_validate(document)


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead])
async def list_document_chunks(
    case_id: UUID,
    document_id: UUID,
    service: DocumentServiceDep,
) -> list[DocumentChunkRead]:
    chunks = await service.list_chunks(case_id, document_id)
    return [DocumentChunkRead.model_validate(chunk) for chunk in chunks]
