from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.db.models import InvestigationRun


class InvestigationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        case_id: UUID,
        objective: str,
        max_retries: int,
    ) -> InvestigationRun:
        run = InvestigationRun(
            case_id=case_id,
            objective=objective,
            state="created",
            current_step="created",
            attempt=0,
            abstained=False,
            plan_json=[],
            evidence_json=[],
            gaps_json=[],
            citations_json=[],
            metadata_json={
                "workflow_version": "phase25-v1",
                "max_retries": max_retries,
            },
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def list_for_case(self, case_id: UUID) -> list[InvestigationRun]:
        result = await self._session.execute(
            select(InvestigationRun)
            .where(InvestigationRun.case_id == case_id)
            .order_by(InvestigationRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_case(
        self,
        *,
        case_id: UUID,
        workflow_id: UUID,
    ) -> InvestigationRun | None:
        result = await self._session.execute(
            select(InvestigationRun).where(
                InvestigationRun.id == workflow_id,
                InvestigationRun.case_id == case_id,
            )
        )
        return result.scalar_one_or_none()

    async def save(self, run: InvestigationRun) -> InvestigationRun:
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def mark_running(
        self,
        run: InvestigationRun,
        *,
        current_step: str,
    ) -> InvestigationRun:
        run.state = "running"
        run.current_step = current_step
        run.started_at = datetime.now(UTC)
        run.completed_at = None
        run.error_message = None
        return await self.save(run)

    async def mark_completed(
        self,
        run: InvestigationRun,
    ) -> InvestigationRun:
        run.state = "completed"
        run.current_step = "completed"
        run.completed_at = datetime.now(UTC)
        run.error_message = None
        return await self.save(run)

    async def mark_failed(
        self,
        run: InvestigationRun,
        *,
        error_message: str,
    ) -> InvestigationRun:
        run.state = "failed"
        run.current_step = "failed"
        run.completed_at = datetime.now(UTC)
        run.error_message = error_message[:4000]
        return await self.save(run)
