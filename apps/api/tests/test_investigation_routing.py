from casemesh.workflows.investigation import choose_next_step
from casemesh.workflows.state import InvestigationState


def test_route_retries_low_confidence_when_budget_remains() -> None:
    state: InvestigationState = {
        "assessment_confidence": "low",
        "assessment_abstained": False,
        "attempt": 0,
        "max_retries": 1,
    }

    assert choose_next_step(state) == "retry_retrieval"


def test_route_identifies_gaps_after_retry_budget_exhausted() -> None:
    state: InvestigationState = {
        "assessment_confidence": "low",
        "assessment_abstained": True,
        "attempt": 1,
        "max_retries": 1,
    }

    assert choose_next_step(state) == "identify_gaps"


def test_route_produces_findings_when_evidence_is_sufficient() -> None:
    state: InvestigationState = {
        "assessment_confidence": "medium",
        "assessment_abstained": False,
        "attempt": 0,
        "max_retries": 1,
    }

    assert choose_next_step(state) == "produce_findings"
