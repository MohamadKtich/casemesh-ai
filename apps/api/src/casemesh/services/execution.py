import hashlib
from uuid import UUID

from fastapi import HTTPException, status

from casemesh.core.config import Settings
from casemesh.execution import (
    ExecutionContext,
    ExecutorRegistry,
)
from casemesh.execution.live import LiveAdapterRegistry
from casemesh.repositories.actions import ActionRepository
from casemesh.repositories.cases import CaseRepository
from casemesh.schemas.actions import (
    ActionExecutionResponse,
    ExecutionMode,
)


class ActionExecutionService:
    def __init__(
        self,
        *,
        settings: Settings,
        action_repository: ActionRepository,
        case_repository: CaseRepository,
    ) -> None:
        self._settings = settings
        self._actions = action_repository
        self._cases = case_repository

        self._dry_run_executors = ExecutorRegistry()
        self._live_adapters = LiveAdapterRegistry()

    async def execute(
        self,
        *,
        case_id: UUID,
        action_request_id: UUID,
        mode: ExecutionMode,
        idempotency_key: str,
        requested_by: str,
    ) -> ActionExecutionResponse:
        action = await self._actions.get(
            case_id=case_id,
            action_request_id=action_request_id,
        )

        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action request not found.",
            )

        if action.status not in {
            "approved",
            "auto_approved",
            "executed",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only approved, auto-approved, or already "
                    "executed actions can enter controlled execution."
                ),
            )

        if action.requires_human_approval:
            if action.approval_id is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Approved action is missing "
                        "approval metadata."
                    ),
                )

            approval = await self._actions.get_approval(
                action.approval_id
            )

            if approval is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Approval record not found.",
                )

            if approval.decision != "approve":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Human approval is required before "
                        "this action can be executed."
                    ),
                )

        try:
            self._enforce_execution_mode(
                mode=mode,
                action_type=action.action_type,
            )

        except HTTPException as exc:
            await self._actions.add_audit(
                case_id=case_id,
                investigation_run_id=(
                    action.investigation_run_id
                ),
                action_request_id=action.id,
                actor_type="operator",
                actor_ref=requested_by,
                event_type="execution_blocked",
                details={
                    "mode": mode,
                    "action_type": action.action_type,
                    "status_code": exc.status_code,
                    "reason": str(exc.detail),
                    "execution_enabled": (
                        self._settings.action_execution_enabled
                    ),
                    "configured_execution_mode": (
                        self._settings.action_execution_mode
                    ),
                    "live_allowlist": list(
                        self._live_allowlist()
                    ),
                    "external_side_effect": False,
                },
            )
            raise

        execution_ref = self._execution_ref(
            mode=mode,
            idempotency_key=idempotency_key,
        )

        if action.external_ref is not None:
            if action.external_ref == execution_ref:
                await self._actions.add_audit(
                    case_id=case_id,
                    investigation_run_id=(
                        action.investigation_run_id
                    ),
                    action_request_id=action.id,
                    actor_type="operator",
                    actor_ref=requested_by,
                    event_type="execution_replayed",
                    details={
                        "mode": mode,
                        "execution_ref": execution_ref,
                        "external_side_effect": False,
                    },
                )

                return ActionExecutionResponse(
                    action_request_id=action.id,
                    case_id=action.case_id,
                    action_type=action.action_type,
                    mode=mode,
                    status="replayed",
                    idempotent_replay=True,
                    external_ref=execution_ref,
                    external_side_effect=False,
                    details={
                        "message": (
                            "This execution request was already "
                            "processed. No additional action "
                            "was performed."
                        ),
                    },
                )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This action request already has a "
                    "different execution reference."
                ),
            )

        await self._actions.add_audit(
            case_id=case_id,
            investigation_run_id=action.investigation_run_id,
            action_request_id=action.id,
            actor_type="operator",
            actor_ref=requested_by,
            event_type="execution_requested",
            details={
                "mode": mode,
                "execution_ref": execution_ref,
                "action_type": action.action_type,
            },
        )

        if mode == "dry_run":
            return await self._execute_dry_run(
                action=action,
                execution_ref=execution_ref,
            )

        return await self._execute_live(
            action=action,
            execution_ref=execution_ref,
            requested_by=requested_by,
        )

    async def _execute_dry_run(
        self,
        *,
        action,
        execution_ref: str,
    ) -> ActionExecutionResponse:
        try:
            executor = self._dry_run_executors.get(
                action.action_type
            )

            context = ExecutionContext(
                case_id=action.case_id,
                action_request_id=action.id,
                action_type=action.action_type,
            )

            outcome = executor.dry_run(
                context=context,
                payload=action.reviewed_payload_json,
            )

        except ValueError as exc:
            await self._actions.add_audit(
                case_id=action.case_id,
                investigation_run_id=(
                    action.investigation_run_id
                ),
                action_request_id=action.id,
                actor_type="system",
                actor_ref="controlled-executor",
                event_type="execution_failed",
                details={
                    "mode": "dry_run",
                    "error": str(exc),
                },
            )

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        if outcome.external_side_effect:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Dry-run executor reported an external "
                    "side effect."
                ),
            )

        action.external_ref = execution_ref
        action.error_message = None

        await self._actions.save_action(action)

        await self._actions.add_audit(
            case_id=action.case_id,
            investigation_run_id=action.investigation_run_id,
            action_request_id=action.id,
            actor_type="system",
            actor_ref="controlled-executor",
            event_type="execution_simulated",
            details={
                "mode": outcome.mode,
                "status": outcome.status,
                "execution_ref": execution_ref,
                "external_side_effect": False,
                "result": outcome.details,
            },
        )

        return ActionExecutionResponse(
            action_request_id=action.id,
            case_id=action.case_id,
            action_type=action.action_type,
            mode="dry_run",
            status="simulated",
            idempotent_replay=False,
            external_ref=execution_ref,
            external_side_effect=False,
            details=outcome.details,
        )

    async def _execute_live(
        self,
        *,
        action,
        execution_ref: str,
        requested_by: str,
    ) -> ActionExecutionResponse:
        case = await self._cases.get(action.case_id)

        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )

        try:
            adapter = self._live_adapters.get(
                action.action_type
            )

            outcome = await adapter.execute(
                case=case,
                payload=action.reviewed_payload_json,
            )

        except LookupError as exc:
            await self._actions.add_audit(
                case_id=action.case_id,
                investigation_run_id=action.investigation_run_id,
                action_request_id=action.id,
                actor_type="operator",
                actor_ref=requested_by,
                event_type="execution_blocked",
                details={
                    "mode": "live",
                    "action_type": action.action_type,
                    "status_code": 501,
                    "reason": str(exc),
                    "external_side_effect": False,
                },
            )

            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=str(exc),
            ) from exc

        except ValueError as exc:
            await self._actions.add_audit(
                case_id=action.case_id,
                investigation_run_id=action.investigation_run_id,
                action_request_id=action.id,
                actor_type="system",
                actor_ref="internal-live-adapter",
                event_type="execution_failed",
                details={
                    "mode": "live",
                    "error": str(exc),
                    "external_side_effect": False,
                },
            )

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        action.external_ref = execution_ref
        action.status = "executed"
        action.error_message = None

        # Case and ActionRequest use the same SQLAlchemy session.
        # save_action() commits both the case status change and the
        # execution metadata in one transaction.
        await self._actions.save_action(action)

        await self._actions.add_audit(
            case_id=action.case_id,
            investigation_run_id=action.investigation_run_id,
            action_request_id=action.id,
            actor_type="system",
            actor_ref="internal-live-adapter",
            event_type="execution_completed",
            details={
                "mode": "live",
                "status": outcome.status,
                "execution_ref": execution_ref,
                "internal_side_effect": (
                    outcome.internal_side_effect
                ),
                "external_side_effect": (
                    outcome.external_side_effect
                ),
                "result": outcome.details,
            },
        )

        return ActionExecutionResponse(
            action_request_id=action.id,
            case_id=action.case_id,
            action_type=action.action_type,
            mode="live",
            status="completed",
            idempotent_replay=False,
            external_ref=execution_ref,
            external_side_effect=(
                outcome.external_side_effect
            ),
            details={
                **outcome.details,
                "internal_side_effect": (
                    outcome.internal_side_effect
                ),
            },
        )

    def _enforce_execution_mode(
        self,
        *,
        mode: ExecutionMode,
        action_type: str,
    ) -> None:
        if mode == "dry_run":
            return

        if not self._settings.action_execution_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Live action execution is disabled by "
                    "ACTION_EXECUTION_ENABLED."
                ),
            )

        if self._settings.action_execution_mode != "live":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Live action execution is blocked because "
                    "ACTION_EXECUTION_MODE is not set to live."
                ),
            )

        if action_type not in self._live_allowlist():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Live execution is not allowed for action "
                    f"type '{action_type}'."
                ),
            )

    def _live_allowlist(self) -> tuple[str, ...]:
        values = (
            value.strip()
            for value
            in self._settings.action_execution_live_allowlist.split(",")
        )

        return tuple(
            value
            for value in values
            if value
        )

    @staticmethod
    def _execution_ref(
        *,
        mode: ExecutionMode,
        idempotency_key: str,
    ) -> str:
        digest = hashlib.sha256(
            idempotency_key.encode("utf-8")
        ).hexdigest()

        return f"{mode}:{digest}"