from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.db.models import CaseDocument
from casemesh.repositories.documents import DocumentRepository


@pytest.mark.asyncio
async def test_set_failed_rolls_back_before_recording_failure() -> None:
    session = Mock(spec=AsyncSession)
    session.rollback = AsyncMock()
    session.commit = AsyncMock()

    document = CaseDocument(
        id=uuid4(),
        case_id=uuid4(),
        filename="evidence.txt",
        storage_uri="data/raw/evidence.txt",
        ingestion_status="processing",
    )
    repository = DocumentRepository(session)

    await repository.set_failed(document, "parser failed")

    session.rollback.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert document.ingestion_status == "failed"
    assert document.ingestion_error == "parser failed"
