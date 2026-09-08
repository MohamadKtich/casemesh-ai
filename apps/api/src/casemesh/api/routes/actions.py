from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.core.config import get_settings
from casemesh.db.session import get_db_session
from casemesh.policy.guardrails import PolicyGuard
from casemesh.repositories.actions import ActionRepository
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.investigations import (
    InvestigationRepository,
)
from casemesh.schemas.actions import (
    ActionExecutionRequest,
    ActionExecutionResponse,
    ActionProposalRequest,
    ActionRequestResponse,
    ApprovalDecisionRequest,
    AuditEventResponse,
)
from casemesh.services.actions import ActionService
from casemesh.services.execution import (
    ActionExecutionService,
)


router = APIRouter()

DbSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


def get_action_service(
    session: DbSession,
) -> ActionService:
    settings = get_settings()

    return ActionService(
        settings=settings,
        case_repository=CaseRepository(session),
        investigation_repository=(
            InvestigationRepository(session)
        ),
        action_repository=ActionRepository(session),
        policy_guard=PolicyGuard(
            allow_internal_note_without_review=(
                settings
                .approval_allow_internal_note_without_review
            )
        ),
    )


def get_action_execution_service(
    session: DbSession,
) -> ActionExecutionService:
    settings = get_settings()

    return ActionExecutionService(
        settings=settings,
        action_repository=ActionRepository(session),
        case_repository=CaseRepository(session),
    )


ActionServiceDep = Annotated[
    ActionService,
    Depends(get_action_service),
]

ActionExecutionServiceDep = Annotated[
    ActionExecutionService,
    Depends(get_action_execution_service),
]


@router.post(
    "/cases/{case_id}/investigations/{workflow_id}/actions",
    response_model=ActionRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["governance"],
)
async def propose_action(
    case_id: UUID,
    workflow_id: UUID,
    payload: ActionProposalRequest,
    service: ActionServiceDep,
) -> ActionRequestResponse:
    return await service.propose(
        case_id=case_id,
        workflow_id=workflow_id,
        action_type=payload.action_type,
        payload=payload.payload,
    )


@router.post(
    "/cases/{case_id}/actions/{action_request_id}/decision",
    response_model=ActionRequestResponse,
    tags=["governance"],
)
async def decide_action(
    case_id: UUID,
    action_request_id: UUID,
    payload: ApprovalDecisionRequest,
    service: ActionServiceDep,
) -> ActionRequestResponse:
    return await service.decide(
        case_id=case_id,
        action_request_id=action_request_id,
        decision=payload.decision,
        reviewer_ref=payload.reviewer_ref,
        comment=payload.comment,
    )


@router.post(
    "/cases/{case_id}/actions/{action_request_id}/execute",
    response_model=ActionExecutionResponse,
    tags=["execution"],
)
async def execute_action(
    case_id: UUID,
    action_request_id: UUID,
    payload: ActionExecutionRequest,
    service: ActionExecutionServiceDep,
) -> ActionExecutionResponse:
    return await service.execute(
        case_id=case_id,
        action_request_id=action_request_id,
        mode=payload.mode,
        idempotency_key=payload.idempotency_key,
        requested_by=payload.requested_by,
    )


@router.get(
    "/cases/{case_id}/actions/{action_request_id}",
    response_model=ActionRequestResponse,
    tags=["governance"],
)
async def get_action(
    case_id: UUID,
    action_request_id: UUID,
    service: ActionServiceDep,
) -> ActionRequestResponse:
    return await service.get(
        case_id=case_id,
        action_request_id=action_request_id,
    )


@router.get(
    "/cases/{case_id}/actions",
    response_model=list[ActionRequestResponse],
    tags=["governance"],
)
async def list_actions(
    case_id: UUID,
    service: ActionServiceDep,
) -> list[ActionRequestResponse]:
    return await service.list(
        case_id=case_id
    )


@router.get(
    "/cases/{case_id}/actions/{action_request_id}/audit-events",
    response_model=list[AuditEventResponse],
    tags=["governance"],
)
async def list_action_audit_events(
    case_id: UUID,
    action_request_id: UUID,
    service: ActionServiceDep,
) -> list[AuditEventResponse]:
    return await service.audit(
        case_id=case_id,
        action_request_id=action_request_id,
    )