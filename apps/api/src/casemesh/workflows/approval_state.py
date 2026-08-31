from typing import TypedDict


class ActionApprovalState(TypedDict, total=False):
    thread_id: str
    action_request_id: str
    case_id: str
    investigation_run_id: str
    action_type: str
    payload: dict[str, object]
    policy_decision: str
    policy_rationale: str
    risk_level: str
    requires_human_approval: bool
    interrupt_question: str
    status: str
    approval_decision: str
    reviewer_ref: str
    comment: str
