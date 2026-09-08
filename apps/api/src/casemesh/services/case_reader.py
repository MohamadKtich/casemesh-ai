from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from casemesh.repositories.cases import CaseRepository


@dataclass(frozen=True)
class CaseSnapshot:
    id: UUID
    case_number: str
    title: str
    status: str
    priority: str
    customer_ref: str | None


class CaseReader(Protocol):
    async def get(
        self,
        case_id: UUID,
    ) -> CaseSnapshot | None:
        """Read basic case information without mutating the case."""


class RepositoryCaseReader:
    def __init__(
        self,
        *,
        repository: CaseRepository,
    ) -> None:
        self._repository = repository

    async def get(
        self,
        case_id: UUID,
    ) -> CaseSnapshot | None:
        case = await self._repository.get(case_id)

        if case is None:
            return None

        return CaseSnapshot(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            status=case.status,
            priority=case.priority,
            customer_ref=case.customer_ref,
        )