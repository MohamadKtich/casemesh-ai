from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.core.exceptions import DuplicateCaseNumberError
from casemesh.db.models import Case


class CaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, case: Case) -> Case:
        self._session.add(case)

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()

            if "cases_case_number_key" in str(exc.orig):
                raise DuplicateCaseNumberError(case.case_number) from exc

            raise

        await self._session.refresh(case)
        return case

    async def list(self) -> list[Case]:
        result = await self._session.execute(select(Case).order_by(Case.created_at.desc()))
        return list(result.scalars().all())

    async def get(self, case_id: UUID) -> Case | None:
        return await self._session.get(Case, case_id)

    async def save(self, case: Case) -> Case:
        await self._session.commit()
        await self._session.refresh(case)
        return case
