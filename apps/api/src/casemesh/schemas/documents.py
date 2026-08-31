from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    filename: str
    content_type: str | None
    sha256: str | None
    ingestion_status: str
    source_type: str
    size_bytes: int
    parser_name: str | None
    text_length: int | None
    ingested_at: datetime | None
    ingestion_error: str | None
    created_at: datetime
    updated_at: datetime


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    case_id: UUID
    chunk_index: int
    content: str
    char_count: int
    metadata_json: dict[str, object]
    created_at: datetime
    updated_at: datetime
