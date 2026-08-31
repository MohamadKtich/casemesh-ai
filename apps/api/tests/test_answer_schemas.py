import pytest
from pydantic import ValidationError

from casemesh.schemas.answers import GroundedAnswerRequest


def test_grounded_answer_request_defaults_to_five_results() -> None:
    request = GroundedAnswerRequest(question="What supports the SLA credit request?")

    assert request.top_k == 5


def test_grounded_answer_request_rejects_large_top_k() -> None:
    with pytest.raises(ValidationError):
        GroundedAnswerRequest(
            question="What supports the SLA credit request?",
            top_k=20,
        )
