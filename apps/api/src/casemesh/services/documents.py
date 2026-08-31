from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from casemesh.core.config import get_settings
from casemesh.core.exceptions import (
    DocumentTooLargeError,
    DuplicateDocumentError,
    UnsupportedDocumentTypeError,
)
from casemesh.db.models import CaseDocument, DocumentChunk
from casemesh.ingestion.chunking import chunk_text
from casemesh.ingestion.parsers import get_parser
from casemesh.ingestion.validation import sanitize_filename, validate_document_extension
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.documents import DocumentRepository
from casemesh.storage.local import LocalDocumentStorage

settings = get_settings()


class DocumentService:
    def __init__(
        self,
        case_repository: CaseRepository,
        document_repository: DocumentRepository,
    ) -> None:
        self._cases = case_repository
        self._documents = document_repository
        self._storage = LocalDocumentStorage(
            Path(settings.document_storage_root),
            settings.max_upload_bytes,
        )

    async def _require_case(self, case_id: UUID) -> None:
        case = await self._cases.get(case_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found",
            )

    async def upload(self, case_id: UUID, upload: UploadFile) -> CaseDocument:
        await self._require_case(case_id)

        original_filename = upload.filename or "document"
        filename = sanitize_filename(original_filename)

        try:
            validate_document_extension(filename)
        except UnsupportedDocumentTypeError as exc:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=str(exc),
            ) from exc

        document_id = uuid4()

        try:
            stored = await self._storage.save_upload(
                case_id=case_id,
                document_id=document_id,
                filename=filename,
                upload=upload,
            )
        except DocumentTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(exc),
            ) from exc

        existing = await self._documents.find_by_sha256(case_id, stored.sha256)
        if existing is not None:
            self._storage.delete_uri(stored.uri)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This document content already exists for the case.",
            )

        document = CaseDocument(
            id=document_id,
            case_id=case_id,
            filename=filename,
            content_type=upload.content_type,
            storage_uri=stored.uri,
            sha256=stored.sha256,
            ingestion_status="pending",
            source_type="upload",
            size_bytes=stored.size_bytes,
        )

        try:
            return await self._documents.create(document)
        except DuplicateDocumentError as exc:
            self._storage.delete_uri(stored.uri)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This document content already exists for the case.",
            ) from exc

    async def list_for_case(self, case_id: UUID) -> list[CaseDocument]:
        await self._require_case(case_id)
        return await self._documents.list_for_case(case_id)

    async def get(self, case_id: UUID, document_id: UUID) -> CaseDocument:
        await self._require_case(case_id)
        document = await self._documents.get_for_case(case_id, document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        return document

    async def ingest(self, case_id: UUID, document_id: UUID) -> CaseDocument:
        document = await self.get(case_id, document_id)
        await self._documents.set_processing(document)

        try:
            path = self._storage.resolve_uri(document.storage_uri)
            parser = get_parser(path)
            text = parser.parse(path).strip()

            if not text:
                raise ValueError("No extractable text was found in the document.")

            chunks = chunk_text(
                text,
                max_chars=settings.chunk_max_chars,
                overlap_chars=settings.chunk_overlap_chars,
            )
            if not chunks:
                raise ValueError("Document produced no chunks.")

            return await self._documents.replace_chunks_and_mark_ready(
                document,
                chunks,
                parser.name,
                len(text),
            )
        except (UnsupportedDocumentTypeError, ValueError) as exc:
            await self._documents.set_failed(document, str(exc))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            await self._documents.set_failed(document, "Unexpected ingestion failure.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document ingestion failed.",
            ) from exc

    async def list_chunks(self, case_id: UUID, document_id: UUID) -> list[DocumentChunk]:
        await self.get(case_id, document_id)
        return await self._documents.list_chunks(document_id)
