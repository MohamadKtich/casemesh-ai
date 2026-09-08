from dataclasses import dataclass
from typing import get_args

from casemesh.db.models import Case
from casemesh.schemas.cases import CaseStatus


@dataclass(frozen=True, slots=True)
class LiveExecutionOutcome:
    status: str
    external_side_effect: bool
    internal_side_effect: bool
    details: dict[str, object]


class UpdateCaseStatusLiveAdapter:
    action_type = "update_case_status"

    async def execute(
        self,
        *,
        case: Case,
        payload: dict[str, object],
    ) -> LiveExecutionOutcome:
        requested_status = payload.get("status")

        if not isinstance(requested_status, str):
            raise ValueError(
                "update_case_status requires a string 'status' value."
            )

        requested_status = requested_status.strip()

        allowed_statuses = set(get_args(CaseStatus))

        if requested_status not in allowed_statuses:
            allowed = ", ".join(sorted(allowed_statuses))

            raise ValueError(
                f"Unsupported case status '{requested_status}'. "
                f"Allowed values: {allowed}."
            )

        previous_status = case.status
        changed = previous_status != requested_status

        if changed:
            case.status = requested_status

        return LiveExecutionOutcome(
            status="completed",
            external_side_effect=False,
            internal_side_effect=changed,
            details={
                "operation": self.action_type,
                "previous_status": previous_status,
                "new_status": requested_status,
                "changed": changed,
                "message": (
                    "Case status updated successfully."
                    if changed
                    else "Case already had the requested status."
                ),
            },
        )


class LiveAdapterRegistry:
    def __init__(self) -> None:
        adapters = (
            UpdateCaseStatusLiveAdapter(),
        )

        self._adapters = {
            adapter.action_type: adapter
            for adapter in adapters
        }

    def get(
        self,
        action_type: str,
    ) -> UpdateCaseStatusLiveAdapter:
        adapter = self._adapters.get(action_type)

        if adapter is None:
            raise LookupError(
                f"No live adapter is registered for action type: "
                f"{action_type}"
            )

        return adapter