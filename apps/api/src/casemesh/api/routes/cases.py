from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.db.session import get_db_session
from casemesh.repositories.cases import CaseRepository
from casemesh.schemas.cases import CaseCreate, CaseRead, CaseUpdate
from casemesh.services.cases import CaseService

router = APIRouter(prefix="/cases", tags=["cases"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_case_service(session: DbSession) -> CaseService:
    return CaseService(CaseRepository(session))


CaseServiceDep = Annotated[CaseService, Depends(get_case_service)]


@router.post(
    "",
    response_model=CaseRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "A case with the same case_number already exists."
        }
    },
)
async def create_case(
    payload: CaseCreate,
    service: CaseServiceDep,
) -> CaseRead:
    case = await service.create(payload)
    return CaseRead.model_validate(case)


@router.get("", response_model=list[CaseRead])
async def list_cases(service: CaseServiceDep) -> list[CaseRead]:
    cases = await service.list()
    return [CaseRead.model_validate(case) for case in cases]


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(
    case_id: UUID,
    service: CaseServiceDep,
) -> CaseRead:
    case = await service.get(case_id)
    return CaseRead.model_validate(case)


@router.patch("/{case_id}", response_model=CaseRead)
async def update_case(
    case_id: UUID,
    payload: CaseUpdate,
    service: CaseServiceDep,
) -> CaseRead:
    case = await service.update(case_id, payload)
    return CaseRead.model_validate(case)
