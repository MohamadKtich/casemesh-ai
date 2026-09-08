from casemesh.execution.base import ActionExecutor
from casemesh.execution.executors import (
    CustomerNotificationExecutor,
    InternalNoteExecutor,
    IssueSlaCreditExecutor,
    UpdateCaseStatusExecutor,
)


class ExecutorRegistry:
    def __init__(self) -> None:
        executors: tuple[ActionExecutor, ...] = (
            IssueSlaCreditExecutor(),
            CustomerNotificationExecutor(),
            UpdateCaseStatusExecutor(),
            InternalNoteExecutor(),
        )

        self._executors = {
            executor.action_type: executor
            for executor in executors
        }

    def get(
        self,
        action_type: str,
    ) -> ActionExecutor:
        executor = self._executors.get(action_type)

        if executor is None:
            raise ValueError(
                f"No controlled executor is registered for action type: "
                f"{action_type}"
            )

        return executor

    def supported_action_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._executors))