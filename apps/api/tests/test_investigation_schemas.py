import pytest
from pydantic import ValidationError

from casemesh.schemas.investigations import InvestigationStartRequest


def test_investigation_start_request_accepts_objective() -> None:
    request = InvestigationStartRequest(
        objective="Determine whether the customer qualifies for SLA relief."
    )

    assert request.objective.startswith("Determine")


def test_investigation_start_request_rejects_short_objective() -> None:
    with pytest.raises(ValidationError):
        InvestigationStartRequest(objective="SLA")
