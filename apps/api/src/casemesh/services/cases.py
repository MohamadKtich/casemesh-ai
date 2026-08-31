from uuid import UUID

from fastapi import HTTPException, status

from casemesh.core.exceptions import DuplicateCaseNumberError
from casemesh.db.models import Case
from casemesh.repositories.cases import CaseRepository
from casemesh.schemas.cases import CaseCreate, CaseUpdate


class CaseService:
    def __init__(self, repository: CaseRepository) -> None:
        self._repository = repository

    async def create(self, payload: CaseCreate) -> Case:
        case = Case(
            case_number=payload.case_number,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            customer_ref=payload.customer_ref,
            status="created",
        )

        try:
            return await self._repository.create(case)
        except DuplicateCaseNumberError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A case with case_number '{exc.case_number}' already exists.",
            ) from exc

    async def list(self) -> list[Case]:
        return await self._repository.list()

    async def get(self, case_id: UUID) -> Case:
        case = await self._repository.get(case_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found",
            )
        return case

    async def update(self, case_id: UUID, payload: CaseUpdate) -> Case:
        case = await self.get(case_id)

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(case, field, value)

        return await self._repository.save(case)
