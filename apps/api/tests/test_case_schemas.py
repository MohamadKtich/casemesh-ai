import pytest
from pydantic import ValidationError

from casemesh.schemas.cases import CaseCreate, CaseUpdate


def test_case_create_defaults() -> None:
    payload = CaseCreate(
        case_number="CASE-001",
        title="Example case",
    )

    assert payload.priority == "normal"
    assert payload.description is None


def test_case_create_rejects_invalid_priority() -> None:
    with pytest.raises(ValidationError):
        CaseCreate(
            case_number="CASE-001",
            title="Example case",
            priority="impossible",  # type: ignore[arg-type]
        )


def test_case_update_is_partial() -> None:
    payload = CaseUpdate(status="investigating")
    assert payload.model_dump(exclude_unset=True) == {"status": "investigating"}
