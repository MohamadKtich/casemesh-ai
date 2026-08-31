from casemesh.workflows.approval import route_policy
from casemesh.workflows.approval_state import ActionApprovalState


def test_policy_block_routes_to_blocked() -> None:
    state: ActionApprovalState = {
        "policy_decision": "block",
    }

    assert route_policy(state) == "blocked"


def test_policy_allow_routes_to_auto_approved() -> None:
    state: ActionApprovalState = {
        "policy_decision": "allow",
    }

    assert route_policy(state) == "auto_approved"


def test_policy_review_routes_to_human_review() -> None:
    state: ActionApprovalState = {
        "policy_decision": "require_approval",
    }

    assert route_policy(state) == "human_review"
