from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from casemesh.core.exceptions import DuplicateCaseNumberError
from casemesh.schemas.cases import CaseCreate
from casemesh.services.cases import CaseService


@pytest.mark.asyncio
async def test_duplicate_case_number_returns_conflict() -> None:
    repository = Mock()
    repository.create = AsyncMock(side_effect=DuplicateCaseNumberError("CASE-001"))
    service = CaseService(repository)

    payload = CaseCreate(
        case_number="CASE-001",
        title="Duplicate case",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create(payload)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == ("A case with case_number 'CASE-001' already exists.")
