import pytest
from pydantic import ValidationError

from casemesh.schemas.actions import (
    ActionProposalRequest,
    ApprovalDecisionRequest,
)


def test_action_proposal_accepts_json_payload() -> None:
    request = ActionProposalRequest(
        action_type="update_case_status",
        payload={"status": "resolved"},
    )

    assert request.payload["status"] == "resolved"


def test_approval_decision_accepts_approve() -> None:
    request = ApprovalDecisionRequest(
        decision="approve",
        reviewer_ref="reviewer-demo",
        comment="Evidence reviewed.",
    )

    assert request.decision == "approve"


def test_approval_decision_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        ApprovalDecisionRequest.model_validate(
            {
                "decision": "maybe",
                "reviewer_ref": "reviewer-demo",
            }
        )
