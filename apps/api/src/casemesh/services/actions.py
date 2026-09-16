import builtins
from collections.abc import Mapping
from typing import Literal, cast
from uuid import UUID

from fastapi import HTTPException, status

from casemesh.alerts import (
    AlertDispatcher,
    AlertEvent,
    AlertSeverity,
)
from casemesh.core.config import Settings
from casemesh.db.models import ActionRequest, Approval, AuditEvent
from casemesh.intelligence.risk_triggers import (
    RiskTriggerContext,
    RiskTriggerDecision,
    RiskTriggerEngine,
)
from casemesh.policy.guardrails import PolicyEvaluation, PolicyGuard
from casemesh.repositories.actions import ActionRepository
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.investigations import InvestigationRepository
from casemesh.schemas.actions import (
    ActionRequestResponse,
    ActionStatus,
    AuditEventResponse,
    PolicyDecision,
    PolicyEvaluationResponse,
    RiskLevel,
)
from casemesh.workflows.approval import ActionApprovalWorkflow
from casemesh.workflows.approval_state import ActionApprovalState
from casemesh.workflows.checkpoints import open_checkpointer


class ActionService:
    def __init__(
        self,
        *,
        settings: Settings,
        case_repository: CaseRepository,
        investigation_repository: InvestigationRepository,
        action_repository: ActionRepository,
        policy_guard: PolicyGuard,
        alert_dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self._settings = settings
        self._cases = case_repository
        self._investigations = investigation_repository
        self._actions = action_repository
        self._policy = policy_guard
        self._risk_trigger_engine = RiskTriggerEngine()
        self._alerts = alert_dispatcher if alert_dispatcher is not None else AlertDispatcher(None)

    async def propose(
        self,
        *,
        case_id: UUID,
        workflow_id: UUID,
        action_type: str,
        payload: dict[str, object],
    ) -> ActionRequestResponse:
        case = await self._cases.get(case_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found",
            )

        investigation = await self._investigations.get_for_case(
            case_id=case_id,
            workflow_id=workflow_id,
        )
        if investigation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Investigation workflow not found",
            )

        if investigation.state != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Only completed investigations can propose governed actions."),
            )

        second_review_requires_human = self._second_review_requires_human_review(
            investigation.metadata_json
        )

        evaluation = self._policy.evaluate(
            action_type=action_type,
            payload=payload,
            investigation_confidence=investigation.confidence,
            investigation_abstained=investigation.abstained,
            citation_count=len(investigation.citations_json),
            second_review_requires_human=(second_review_requires_human),
        )

        action_trigger_decision = self._risk_trigger_engine.evaluate(
            RiskTriggerContext(
                action_type=action_type,
                action_risk_level=(evaluation.risk_level),
            )
        )

        risk_trigger_requires_human = bool(action_trigger_decision.triggers)

        if risk_trigger_requires_human:
            evaluation = self._policy.evaluate(
                action_type=action_type,
                payload=payload,
                investigation_confidence=(investigation.confidence),
                investigation_abstained=(investigation.abstained),
                citation_count=len(investigation.citations_json),
                second_review_requires_human=(second_review_requires_human),
                risk_trigger_requires_human=True,
            )

        action, approval = await self._actions.create(
            case_id=case_id,
            investigation=investigation,
            action_type=action_type,
            payload=payload,
            policy_decision=evaluation.decision,
            policy_rationale=evaluation.rationale,
            risk_level=evaluation.risk_level,
            requires_human_approval=evaluation.requires_human_approval,
        )

        await self._actions.add_audit(
            case_id=case_id,
            investigation_run_id=investigation.id,
            action_request_id=action.id,
            actor_type="system",
            actor_ref="policy-guard",
            event_type="policy_evaluated",
            details=self._policy_details(
                evaluation,
                action_trigger_decision,
            ),
        )

        if evaluation.decision == "block":
            action.status = "blocked"
            await self._actions.save_action(action)
            await self._actions.add_audit(
                case_id=case_id,
                investigation_run_id=investigation.id,
                action_request_id=action.id,
                actor_type="system",
                actor_ref="policy-guard",
                event_type="action_blocked",
                details={
                    "rationale": evaluation.rationale,
                },
            )
            return self._response(
                action=action,
                approval=approval,
                interrupt_payload=None,
            )

        initial_state = self._initial_state(
            action=action,
            investigation_run_id=investigation.id,
            evaluation=evaluation,
        )

        try:
            async with open_checkpointer(self._settings) as checkpointer:
                workflow = ActionApprovalWorkflow(
                    checkpointer=checkpointer,
                )
                result = await workflow.start(initial_state)
        except Exception as exc:
            action.status = "failed"
            action.error_message = str(exc)
            await self._actions.save_action(action)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": "Approval workflow failed.",
                    "action_request_id": str(action.id),
                },
            ) from exc

        if evaluation.decision == "allow":
            graph_status = result.get("status")
            if graph_status != "auto_approved":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Policy-allowed action did not auto-approve.",
                )
            action.status = "auto_approved"
            await self._actions.save_action(action)
            await self._actions.add_audit(
                case_id=case_id,
                investigation_run_id=investigation.id,
                action_request_id=action.id,
                actor_type="system",
                actor_ref="approval-workflow",
                event_type="action_auto_approved",
                details={
                    "execution_enabled": False,
                },
            )
            return self._response(
                action=action,
                approval=approval,
                interrupt_payload=None,
            )

        if "__interrupt__" not in result:
            action.status = "failed"
            action.error_message = "Expected human-approval interrupt was not emitted."
            await self._actions.save_action(action)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Human approval interrupt was not emitted.",
            )

        action.status = "awaiting_approval"
        await self._actions.save_action(action)

        interrupt_payload = ActionApprovalWorkflow.build_interrupt_payload(initial_state)

        await self._actions.add_audit(
            case_id=case_id,
            investigation_run_id=investigation.id,
            action_request_id=action.id,
            actor_type="system",
            actor_ref="approval-workflow",
            event_type="approval_requested",
            details=interrupt_payload,
        )

        approval_alert = self._approval_required_alert_event(
            case_id=case_id,
            investigation_run_id=(investigation.id),
            action_request_id=action.id,
            risk_level=(evaluation.risk_level),
            second_review_requires_human=(second_review_requires_human),
            action_trigger_decision=(action_trigger_decision),
        )

        await self._alerts.dispatch(approval_alert)

        return self._response(
            action=action,
            approval=approval,
            interrupt_payload=interrupt_payload,
        )

    async def decide(
        self,
        *,
        case_id: UUID,
        action_request_id: UUID,
        decision: Literal["approve", "reject"],
        reviewer_ref: str,
        comment: str | None,
    ) -> ActionRequestResponse:
        action = await self._actions.get(
            case_id=case_id,
            action_request_id=action_request_id,
        )
        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action request not found",
            )

        if action.status != "awaiting_approval":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("This action request is not waiting for human approval."),
            )

        if action.approval_id is None or action.thread_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Approval workflow metadata is incomplete.",
            )

        approval = await self._actions.get_approval(action.approval_id)
        if approval is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Approval record not found.",
            )

        try:
            async with open_checkpointer(self._settings) as checkpointer:
                workflow = ActionApprovalWorkflow(
                    checkpointer=checkpointer,
                )
                result = await workflow.resume(
                    thread_id=action.thread_id,
                    decision=decision,
                    reviewer_ref=reviewer_ref,
                    comment=comment,
                )
        except Exception as exc:
            action.status = "failed"
            action.error_message = str(exc)
            await self._actions.save_action(action)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": "Approval resume failed.",
                    "action_request_id": str(action.id),
                },
            ) from exc

        expected_status = "approved" if decision == "approve" else "rejected"
        if result.get("status") != expected_status:
            action.status = "failed"
            action.error_message = "Approval graph returned an invalid status."
            await self._actions.save_action(action)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Approval workflow returned an invalid status.",
            )

        action, approval = await self._actions.save_decision(
            action=action,
            approval=approval,
            decision=decision,
            reviewer_ref=reviewer_ref,
            comment=comment,
        )

        await self._actions.add_audit(
            case_id=case_id,
            investigation_run_id=action.investigation_run_id,
            action_request_id=action.id,
            actor_type="human",
            actor_ref=reviewer_ref,
            event_type=("approval_approved" if decision == "approve" else "approval_rejected"),
            details={
                "decision": decision,
                "comment": comment or "",
                "execution_enabled": False,
            },
        )

        return self._response(
            action=action,
            approval=approval,
            interrupt_payload=None,
        )

    async def get(
        self,
        *,
        case_id: UUID,
        action_request_id: UUID,
    ) -> ActionRequestResponse:
        action = await self._actions.get(
            case_id=case_id,
            action_request_id=action_request_id,
        )
        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action request not found",
            )

        approval = (
            await self._actions.get_approval(action.approval_id)
            if action.approval_id is not None
            else None
        )
        return self._response(
            action=action,
            approval=approval,
            interrupt_payload=None,
        )

    async def list(
        self,
        *,
        case_id: UUID,
    ) -> builtins.list[ActionRequestResponse]:
        case = await self._cases.get(case_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found",
            )

        actions = await self._actions.list_for_case(case_id)
        responses: builtins.list[ActionRequestResponse] = []

        for action in actions:
            approval = (
                await self._actions.get_approval(action.approval_id)
                if action.approval_id is not None
                else None
            )
            responses.append(
                self._response(
                    action=action,
                    approval=approval,
                    interrupt_payload=None,
                )
            )

        return responses

    async def audit(
        self,
        *,
        case_id: UUID,
        action_request_id: UUID,
    ) -> builtins.list[AuditEventResponse]:
        action = await self._actions.get(
            case_id=case_id,
            action_request_id=action_request_id,
        )
        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action request not found",
            )

        events = await self._actions.list_audit_for_action(
            case_id=case_id,
            action_request_id=action_request_id,
        )
        return [self._audit_response(event) for event in events]

    @staticmethod
    def _approval_required_alert_event(
        *,
        case_id: UUID,
        investigation_run_id: UUID,
        action_request_id: UUID,
        risk_level: str,
        second_review_requires_human: bool,
        action_trigger_decision: RiskTriggerDecision,
    ) -> AlertEvent:
        reason_codes = [str(code) for code in action_trigger_decision.reason_codes]

        if second_review_requires_human and "SECOND_REVIEW_REQUIRES_HUMAN" not in reason_codes:
            reason_codes.append("SECOND_REVIEW_REQUIRES_HUMAN")

        if not reason_codes:
            reason_codes.append("POLICY_REQUIRES_APPROVAL")

        severity: AlertSeverity

        if risk_level == "critical":
            severity = "critical"
        elif risk_level == "high":
            severity = "high"
        else:
            severity = "warning"

        return AlertEvent(
            event_type="APPROVAL_REQUIRED",
            severity=severity,
            source="action",
            case_id=case_id,
            investigation_run_id=(investigation_run_id),
            action_request_id=(action_request_id),
            reason_codes=tuple(reason_codes),
            risk_level=risk_level,
            status="awaiting_approval",
        )

    @staticmethod
    def _second_review_requires_human_review(
        metadata: Mapping[str, object] | None,
    ) -> bool:
        """Interpret persisted second-review state conservatively.

        Absence means the legacy investigation path was used.
        Once a second-review record exists, only a completed
        review with an effective continue route may preserve
        normal policy behavior. Malformed or incomplete state
        fails closed to human approval.
        """

        if not metadata:
            return False

        if "second_review" not in metadata:
            return False

        raw_review = metadata.get("second_review")

        if not isinstance(
            raw_review,
            Mapping,
        ):
            return True

        status = raw_review.get("status")

        effective_route = raw_review.get("effective_route")

        return not (status == "completed" and effective_route == "continue")

    def _initial_state(
        self,
        *,
        action: ActionRequest,
        investigation_run_id: UUID,
        evaluation: PolicyEvaluation,
    ) -> ActionApprovalState:
        if action.thread_id is None:
            raise RuntimeError("Action request thread_id was not created.")

        return {
            "thread_id": action.thread_id,
            "action_request_id": str(action.id),
            "case_id": str(action.case_id),
            "investigation_run_id": str(investigation_run_id),
            "action_type": action.action_type,
            "payload": action.payload_json,
            "policy_decision": evaluation.decision,
            "policy_rationale": evaluation.rationale,
            "risk_level": evaluation.risk_level,
            "requires_human_approval": (evaluation.requires_human_approval),
            "interrupt_question": (self._settings.approval_interrupt_question),
            "status": "pending",
        }

    @staticmethod
    @staticmethod
    def _policy_details(
        evaluation: PolicyEvaluation,
        action_trigger_decision: RiskTriggerDecision | None = None,
    ) -> dict[str, object]:
        details: dict[str, object] = {
            "decision": evaluation.decision,
            "risk_level": evaluation.risk_level,
            "requires_human_approval": (evaluation.requires_human_approval),
            "rationale": evaluation.rationale,
        }

        if action_trigger_decision is not None:
            details["action_risk_triggers"] = {
                "human_review_signal": bool(action_trigger_decision.triggers),
                "reason_codes": [str(code) for code in action_trigger_decision.reason_codes],
                "triggers": [
                    {
                        "code": trigger.code,
                        "source": trigger.source,
                        "rationale": trigger.rationale,
                    }
                    for trigger in action_trigger_decision.triggers
                ],
                "bedrock_action_review_performed": False,
            }

        return details

    @staticmethod
    def _response(
        *,
        action: ActionRequest,
        approval: Approval | None,
        interrupt_payload: dict[str, object] | None,
    ) -> ActionRequestResponse:
        action_status = cast(ActionStatus, action.status)
        policy_decision = cast(PolicyDecision, action.policy_decision)
        risk_level = cast(RiskLevel, action.risk_level or "high")

        return ActionRequestResponse(
            action_request_id=action.id,
            case_id=action.case_id,
            investigation_run_id=action.investigation_run_id,
            resolution_draft_id=action.resolution_draft_id,
            approval_id=action.approval_id,
            thread_id=action.thread_id,
            action_type=action.action_type,
            status=action_status,
            policy=PolicyEvaluationResponse(
                decision=policy_decision,
                risk_level=risk_level,
                requires_human_approval=(action.requires_human_approval),
                rationale=action.policy_rationale or "",
            ),
            payload=action.payload_json,
            reviewed_payload=action.reviewed_payload_json,
            approval_decision=(approval.decision if approval is not None else None),
            reviewer_ref=(approval.reviewer_ref if approval is not None else None),
            approval_comment=(approval.comment if approval is not None else None),
            interrupt=interrupt_payload,
            execution_enabled=False,
            error_message=action.error_message,
            created_at=action.created_at,
            updated_at=action.updated_at,
        )

    @staticmethod
    def _audit_response(
        event: AuditEvent,
    ) -> AuditEventResponse:
        return AuditEventResponse(
            id=event.id,
            case_id=event.case_id,
            investigation_run_id=event.investigation_run_id,
            action_request_id=event.action_request_id,
            actor_type=event.actor_type,
            actor_ref=event.actor_ref,
            event_type=event.event_type,
            details=event.details_json,
            created_at=event.created_at,
        )
