from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.db.models import (
    ActionRequest,
    Approval,
    AuditEvent,
    InvestigationRun,
    ResolutionDraft,
)


class ActionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        case_id: UUID,
        investigation: InvestigationRun,
        action_type: str,
        payload: dict[str, object],
        policy_decision: str,
        policy_rationale: str,
        risk_level: str,
        requires_human_approval: bool,
    ) -> tuple[ActionRequest, Approval | None]:
        resolution = ResolutionDraft(
            case_id=case_id,
            investigation_run_id=investigation.id,
            decision=f"proposed:{action_type}",
            reasoning_summary=(
                investigation.findings_text
                or investigation.assessment_text
                or "No grounded finding was available."
            ),
            confidence=self._confidence_score(investigation.confidence),
            recommended_credit_percent=self._credit_percent(
                action_type=action_type,
                payload=payload,
            ),
            citations_json=investigation.citations_json,
        )
        self._session.add(resolution)
        await self._session.flush()

        approval: Approval | None = None
        if requires_human_approval:
            approval = Approval(
                case_id=case_id,
                resolution_draft_id=resolution.id,
                decision="pending",
                metadata_json={
                    "policy_decision": policy_decision,
                    "risk_level": risk_level,
                    "policy_rationale": policy_rationale,
                },
            )
            self._session.add(approval)
            await self._session.flush()

        action = ActionRequest(
            case_id=case_id,
            investigation_run_id=investigation.id,
            resolution_draft_id=resolution.id,
            approval_id=approval.id if approval is not None else None,
            action_type=action_type,
            status="pending",
            policy_decision=policy_decision,
            policy_rationale=policy_rationale,
            risk_level=risk_level,
            requires_human_approval=requires_human_approval,
            payload_json=payload,
            reviewed_payload_json=payload,
        )
        self._session.add(action)
        await self._session.flush()

        action.thread_id = f"action:{action.id}"

        await self._session.commit()
        await self._session.refresh(action)
        if approval is not None:
            await self._session.refresh(approval)

        return action, approval

    async def get(
        self,
        *,
        case_id: UUID,
        action_request_id: UUID,
    ) -> ActionRequest | None:
        result = await self._session.execute(
            select(ActionRequest).where(
                ActionRequest.id == action_request_id,
                ActionRequest.case_id == case_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_case(
        self,
        case_id: UUID,
    ) -> list[ActionRequest]:
        result = await self._session.execute(
            select(ActionRequest)
            .where(ActionRequest.case_id == case_id)
            .order_by(ActionRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_approval(
        self,
        approval_id: UUID,
    ) -> Approval | None:
        result = await self._session.execute(select(Approval).where(Approval.id == approval_id))
        return result.scalar_one_or_none()

    async def save_action(
        self,
        action: ActionRequest,
    ) -> ActionRequest:
        await self._session.commit()
        await self._session.refresh(action)
        return action

    async def save_decision(
        self,
        *,
        action: ActionRequest,
        approval: Approval,
        decision: str,
        reviewer_ref: str,
        comment: str | None,
    ) -> tuple[ActionRequest, Approval]:
        approval.decision = decision
        approval.reviewer_ref = reviewer_ref
        approval.comment = comment
        approval.decided_at = datetime.now(UTC)

        action.status = "approved" if decision == "approve" else "rejected"
        action.error_message = None

        await self._session.commit()
        await self._session.refresh(action)
        await self._session.refresh(approval)
        return action, approval

    async def add_audit(
        self,
        *,
        case_id: UUID,
        investigation_run_id: UUID | None,
        action_request_id: UUID | None,
        actor_type: str,
        actor_ref: str | None,
        event_type: str,
        details: dict[str, object],
    ) -> AuditEvent:
        event = AuditEvent(
            case_id=case_id,
            investigation_run_id=investigation_run_id,
            action_request_id=action_request_id,
            actor_type=actor_type,
            actor_ref=actor_ref,
            event_type=event_type,
            details_json=details,
        )
        self._session.add(event)
        await self._session.commit()
        await self._session.refresh(event)
        return event

    async def list_audit_for_action(
        self,
        *,
        case_id: UUID,
        action_request_id: UUID,
    ) -> list[AuditEvent]:
        result = await self._session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.case_id == case_id,
                AuditEvent.action_request_id == action_request_id,
            )
            .order_by(AuditEvent.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    def _confidence_score(confidence: str | None) -> float | None:
        values = {
            "low": 0.25,
            "medium": 0.60,
            "high": 0.90,
        }
        if confidence is None:
            return None
        return values.get(confidence)

    @staticmethod
    def _credit_percent(
        *,
        action_type: str,
        payload: dict[str, object],
    ) -> float | None:
        if action_type != "issue_sla_credit":
            return None

        value = payload.get("credit_percent")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)
