from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.core.exceptions import DuplicateDocumentError
from casemesh.db.models import CaseDocument, DocumentChunk


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document: CaseDocument) -> CaseDocument:
        self._session.add(document)

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if "uq_case_documents_case_sha256" in str(exc.orig):
                raise DuplicateDocumentError(document.sha256 or "") from exc
            raise

        await self._session.refresh(document)
        return document

    async def list_for_case(self, case_id: UUID) -> list[CaseDocument]:
        result = await self._session.execute(
            select(CaseDocument)
            .where(CaseDocument.case_id == case_id)
            .order_by(CaseDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_case(self, case_id: UUID, document_id: UUID) -> CaseDocument | None:
        result = await self._session.execute(
            select(CaseDocument).where(
                CaseDocument.case_id == case_id,
                CaseDocument.id == document_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_sha256(self, case_id: UUID, sha256: str) -> CaseDocument | None:
        result = await self._session.execute(
            select(CaseDocument).where(
                CaseDocument.case_id == case_id,
                CaseDocument.sha256 == sha256,
            )
        )
        return result.scalar_one_or_none()

    async def set_processing(self, document: CaseDocument) -> None:
        document.ingestion_status = "processing"
        document.ingestion_error = None
        await self._session.commit()

    async def set_failed(self, document: CaseDocument, error: str) -> None:
        # A previous flush/commit may have failed. Always return the session
        # to a clean transactional state before recording the ingestion failure.
        await self._session.rollback()
        document.ingestion_status = "failed"
        document.ingestion_error = error[:2000]
        await self._session.commit()

    async def replace_chunks_and_mark_ready(
        self,
        document: CaseDocument,
        chunks: Sequence[str],
        parser_name: str,
        text_length: int,
    ) -> CaseDocument:
        await self._session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )

        for index, content in enumerate(chunks):
            self._session.add(
                DocumentChunk(
                    document_id=document.id,
                    case_id=document.case_id,
                    chunk_index=index,
                    content=content,
                    char_count=len(content),
                    metadata_json={
                        "document_filename": document.filename,
                        "chunk_index": index,
                    },
                )
            )

        document.parser_name = parser_name
        document.text_length = text_length
        document.ingestion_status = "ready"
        document.ingested_at = datetime.now(UTC)
        document.ingestion_error = None

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        await self._session.refresh(document)
        return document

    async def list_chunks(self, document_id: UUID) -> list[DocumentChunk]:
        result = await self._session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(result.scalars().all())
