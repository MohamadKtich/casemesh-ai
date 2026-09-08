from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    case_id: UUID
    action_request_id: UUID
    action_type: str


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    mode: str
    status: str
    external_side_effect: bool
    details: dict[str, object]


class ActionExecutor(Protocol):
    action_type: str

    def dry_run(
        self,
        *,
        context: ExecutionContext,
        payload: dict[str, object],
    ) -> ExecutionOutcome: ...