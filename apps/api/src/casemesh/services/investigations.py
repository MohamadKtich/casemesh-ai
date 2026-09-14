from typing import Literal, cast
from uuid import UUID

from fastapi import HTTPException, status

from casemesh.core.config import Settings
from casemesh.db.models import InvestigationRun
from casemesh.intelligence.contracts import SecondReviewProvider
from casemesh.repositories.investigations import InvestigationRepository
from casemesh.schemas.investigations import (
    InvestigationCitation,
    InvestigationEvidenceRef,
    InvestigationGap,
    InvestigationPlanStep,
    InvestigationRunResponse,
)
from casemesh.services.answers import AnswerService
from casemesh.services.case_reader import CaseReader
from casemesh.services.retrieval_contract import RetrievalSearcher
from casemesh.workflows.investigation import InvestigationWorkflow
from casemesh.workflows.state import InvestigationState


class InvestigationService:
    def __init__(
        self,
        *,
        settings: Settings,
        case_reader: CaseReader,
        investigation_repository: InvestigationRepository,
        retrieval_service: RetrievalSearcher,
        answer_service: AnswerService,
        second_review_provider: SecondReviewProvider | None = None,
    ) -> None:
        self._settings = settings
        self._cases = case_reader
        self._investigations = investigation_repository
        self._retrieval = retrieval_service
        self._answers = answer_service
        self._second_review_provider = second_review_provider

    async def start(
        self,
        *,
        case_id: UUID,
        objective: str,
    ) -> InvestigationRunResponse:
        case = await self._cases.get(case_id)

        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found",
            )

        run = await self._investigations.create(
            case_id=case_id,
            objective=objective,
            max_retries=self._settings.workflow_max_retries,
        )

        workflow = InvestigationWorkflow(
            run=run,
            settings=self._settings,
            case_reader=self._cases,
            investigation_repository=self._investigations,
            retrieval_service=self._retrieval,
            answer_service=self._answers,
            second_review_provider=(self._second_review_provider),
        )

        initial_state: InvestigationState = {
            "workflow_id": run.id,
            "case_id": case_id,
            "objective": objective,
            "status": "created",
            "current_step": "created",
            "attempt": 0,
            "max_retries": self._settings.workflow_max_retries,
            "search_query": objective,
            "second_review_requested": False,
        }

        try:
            await workflow.run(initial_state)

        except HTTPException as exc:
            await self._investigations.mark_failed(
                run,
                error_message=str(exc.detail),
            )
            raise

        except Exception as exc:
            await self._investigations.mark_failed(
                run,
                error_message=str(exc),
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": "Investigation workflow failed.",
                    "workflow_id": str(run.id),
                },
            ) from exc

        return self._to_response(run)

    async def get(
        self,
        *,
        case_id: UUID,
        workflow_id: UUID,
    ) -> InvestigationRunResponse:
        run = await self._investigations.get_for_case(
            case_id=case_id,
            workflow_id=workflow_id,
        )

        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Investigation workflow not found",
            )

        return self._to_response(run)

    async def list(
        self,
        *,
        case_id: UUID,
    ) -> list[InvestigationRunResponse]:
        case = await self._cases.get(case_id)

        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found",
            )

        runs = await self._investigations.list_for_case(case_id)

        return [self._to_response(run) for run in runs]

    @staticmethod
    def _to_response(
        run: InvestigationRun,
    ) -> InvestigationRunResponse:
        run_state = cast(
            Literal[
                "created",
                "running",
                "completed",
                "failed",
            ],
            run.state,
        )

        run_confidence = cast(
            Literal[
                "low",
                "medium",
                "high",
            ]
            | None,
            run.confidence,
        )

        return InvestigationRunResponse(
            workflow_id=run.id,
            case_id=run.case_id,
            objective=run.objective,
            state=run_state,
            current_step=run.current_step,
            attempt=run.attempt,
            confidence=run_confidence,
            abstained=run.abstained,
            analysis=run.analysis_text,
            assessment=run.assessment_text,
            findings=run.findings_text,
            plan=[InvestigationPlanStep.model_validate(item) for item in run.plan_json],
            evidence=[InvestigationEvidenceRef.model_validate(item) for item in run.evidence_json],
            gaps=[InvestigationGap.model_validate(item) for item in run.gaps_json],
            citations=[InvestigationCitation.model_validate(item) for item in run.citations_json],
            error_message=run.error_message,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
