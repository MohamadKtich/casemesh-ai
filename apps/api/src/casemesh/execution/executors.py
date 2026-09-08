from casemesh.execution.base import (
    ExecutionContext,
    ExecutionOutcome,
)


class IssueSlaCreditExecutor:
    action_type = "issue_sla_credit"

    def dry_run(
        self,
        *,
        context: ExecutionContext,
        payload: dict[str, object],
    ) -> ExecutionOutcome:
        credit_percent = payload.get("credit_percent")

        if isinstance(credit_percent, bool) or not isinstance(
            credit_percent,
            (int, float),
        ):
            raise ValueError("credit_percent must be numeric.")

        credit_percent = float(credit_percent)

        if credit_percent <= 0 or credit_percent > 100:
            raise ValueError(
                "credit_percent must be greater than 0 and no more than 100."
            )

        return ExecutionOutcome(
            mode="dry_run",
            status="simulated",
            external_side_effect=False,
            details={
                "operation": self.action_type,
                "credit_percent": credit_percent,
                "would_issue_credit": True,
                "message": (
                    "Dry run completed. "
                    "No SLA credit was issued to an external system."
                ),
            },
        )


class CustomerNotificationExecutor:
    action_type = "send_customer_notification"

    def dry_run(
        self,
        *,
        context: ExecutionContext,
        payload: dict[str, object],
    ) -> ExecutionOutcome:
        return ExecutionOutcome(
            mode="dry_run",
            status="simulated",
            external_side_effect=False,
            details={
                "operation": self.action_type,
                "payload_keys": sorted(payload.keys()),
                "would_send_notification": True,
                "message": (
                    "Dry run completed. "
                    "No customer notification was sent."
                ),
            },
        )


class UpdateCaseStatusExecutor:
    action_type = "update_case_status"

    def dry_run(
        self,
        *,
        context: ExecutionContext,
        payload: dict[str, object],
    ) -> ExecutionOutcome:
        requested_status = payload.get("status")

        if not isinstance(requested_status, str) or not requested_status.strip():
            raise ValueError(
                "A non-empty status is required for update_case_status."
            )

        return ExecutionOutcome(
            mode="dry_run",
            status="simulated",
            external_side_effect=False,
            details={
                "operation": self.action_type,
                "requested_status": requested_status.strip(),
                "would_update_case_status": True,
                "message": (
                    "Dry run completed. "
                    "The case status was not changed."
                ),
            },
        )


class InternalNoteExecutor:
    action_type = "create_internal_note"

    def dry_run(
        self,
        *,
        context: ExecutionContext,
        payload: dict[str, object],
    ) -> ExecutionOutcome:
        return ExecutionOutcome(
            mode="dry_run",
            status="simulated",
            external_side_effect=False,
            details={
                "operation": self.action_type,
                "payload_keys": sorted(payload.keys()),
                "would_create_internal_note": True,
                "message": (
                    "Dry run completed. "
                    "No internal note was created."
                ),
            },
        )