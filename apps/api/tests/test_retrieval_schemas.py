import pytest
from pydantic import ValidationError

from casemesh.schemas.retrieval import RetrievalSearchRequest


def test_retrieval_request_defaults_to_five_results() -> None:
    request = RetrievalSearchRequest(query="SLA outage evidence")

    assert request.top_k == 5


def test_retrieval_request_rejects_excessive_top_k() -> None:
    with pytest.raises(ValidationError):
        RetrievalSearchRequest(query="SLA outage evidence", top_k=100)
