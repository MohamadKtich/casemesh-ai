from uuid import uuid4

from casemesh.workflows.state import InvestigationState


def test_investigation_state_accepts_workflow_identity() -> None:
    workflow_id = uuid4()
    case_id = uuid4()

    state: InvestigationState = {
        "workflow_id": workflow_id,
        "case_id": case_id,
        "objective": "Assess the SLA credit request.",
        "attempt": 0,
        "max_retries": 1,
    }

    assert state["workflow_id"] == workflow_id
    assert state["case_id"] == case_id
