from typing import Literal, cast
from uuid import UUID

from fastapi import HTTPException, status

from casemesh.alerts import AlertDispatcher
from casemesh.core.config import Settings
from casemesh.db.models import InvestigationRun
from casemesh.intelligence.contracts import SecondReviewProvider
from casemesh.repositories.investigations import InvestigationRepository
from casemesh.schemas.investigations import (
    InvestigationCitation,
    InvestigationEvidenceRef,
    InvestigationGap,
    InvestigationPlanStep,
    InvestigationRiskTriggerSummary,
    InvestigationRunResponse,
    InvestigationSecondReviewSummary,
)
from casemesh.services.answers import AnswerService
from casemesh.services.case_reader import CaseReader
from casemesh.services.retrieval_contract import RetrievalSearcher
from casemesh.workflows.investigation import InvestigationWorkflow
from casemesh.workflows.state import InvestigationState

_SECOND_REVIEW_STATUSES = frozenset(
    {
        "completed",
        "unavailable",
        "failed",
        "budget_exhausted",
        "guardrail_blocked",
        "guardrail_failed",
    }
)

_SECOND_REVIEW_AGREEMENTS = frozenset(
    {
        "agree",
        "disagree",
        "uncertain",
    }
)

_SECOND_REVIEW_RISK_LEVELS = frozenset(
    {
        "low",
        "medium",
        "high",
        "critical",
    }
)

_SECOND_REVIEW_ROUTES = frozenset(
    {
        "continue",
        "human_review",
    }
)


def _safe_reason_codes(
    value: object,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        return []

    reason_codes: list[str] = []

    for item in value:
        if not isinstance(
            item,
            str,
        ):
            continue

        normalized = item.strip()

        if not normalized or normalized in reason_codes:
            continue

        reason_codes.append(normalized)

    return reason_codes


def _safe_enum_value(
    value: object,
    *,
    allowed_values: frozenset[str],
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = value.strip()

    if normalized not in allowed_values:
        return None

    return normalized


def _risk_trigger_summary(
    metadata: object,
) -> InvestigationRiskTriggerSummary | None:
    if not isinstance(
        metadata,
        dict,
    ):
        return None

    raw_summary = metadata.get("risk_triggers")

    if not isinstance(
        raw_summary,
        dict,
    ):
        return None

    raw_requested = raw_summary.get("request_second_review")

    second_review_requested = (
        raw_requested
        if isinstance(
            raw_requested,
            bool,
        )
        else False
    )

    return InvestigationRiskTriggerSummary(
        second_review_requested=(second_review_requested),
        reason_codes=_safe_reason_codes(raw_summary.get("reason_codes")),
    )


def _second_review_summary(
    metadata: object,
) -> InvestigationSecondReviewSummary | None:
    if not isinstance(
        metadata,
        dict,
    ):
        return None

    raw_summary = metadata.get("second_review")

    if not isinstance(
        raw_summary,
        dict,
    ):
        return None

    status_value = _safe_enum_value(
        raw_summary.get("status"),
        allowed_values=_SECOND_REVIEW_STATUSES,
    )

    agreement_value = _safe_enum_value(
        raw_summary.get("agreement"),
        allowed_values=_SECOND_REVIEW_AGREEMENTS,
    )

    risk_level_value = _safe_enum_value(
        raw_summary.get("risk_level"),
        allowed_values=_SECOND_REVIEW_RISK_LEVELS,
    )

    provider_route_value = _safe_enum_value(
        raw_summary.get("provider_route"),
        allowed_values=_SECOND_REVIEW_ROUTES,
    )

    effective_route_value = _safe_enum_value(
        raw_summary.get("effective_route"),
        allowed_values=_SECOND_REVIEW_ROUTES,
    )

    raw_forced_human_review = raw_summary.get("forced_human_review")

    forced_human_review = (
        raw_forced_human_review
        if isinstance(
            raw_forced_human_review,
            bool,
        )
        else False
    )

    guardrail_decision: str | None = None

    if status_value == "guardrail_blocked":
        guardrail_decision = "blocked"

    elif status_value == "guardrail_failed":
        guardrail_decision = "failed"

    return InvestigationSecondReviewSummary.model_validate(
        {
            "status": status_value,
            "agreement": agreement_value,
            "risk_level": risk_level_value,
            "provider_route": provider_route_value,
            "effective_route": effective_route_value,
            "forced_human_review": forced_human_review,
            "reason_codes": _safe_reason_codes(raw_summary.get("reason_codes")),
            "guardrail_decision": guardrail_decision,
        }
    )


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
        alert_dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self._settings = settings
        self._cases = case_reader
        self._investigations = investigation_repository
        self._retrieval = retrieval_service
        self._answers = answer_service
        self._second_review_provider = second_review_provider
        self._alert_dispatcher = (
            alert_dispatcher if alert_dispatcher is not None else AlertDispatcher(None)
        )

    async def start(
        self,
        *,
        case_id: UUID,
        objective: str,
        manual_second_review_requested: bool = False,
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
            alert_dispatcher=self._alert_dispatcher,
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
            "manual_second_review_requested": manual_second_review_requested,
            "evidence_conflict": False,
            "prompt_injection_signal": False,
            "security_flags": [],
            "risk_trigger_codes": [],
            "risk_triggers": {},
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
            risk_triggers=_risk_trigger_summary(run.metadata_json),
            second_review=_second_review_summary(run.metadata_json),
            error_message=run.error_message,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
