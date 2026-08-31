from uuid import UUID

from pydantic import BaseModel, Field


class EmbeddingHealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    dimension: int
    model_available: bool | None = None
    detail: str | None = None


class DocumentEmbeddingResponse(BaseModel):
    case_id: UUID
    document_id: UUID
    provider: str
    model: str
    dimension: int
    chunks_embedded: int


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    metadata_json: dict[str, object]
    hybrid_score: float
    vector_rank: int | None
    keyword_rank: int | None
    vector_similarity: float | None
    keyword_score: float | None


class RetrievalSearchResponse(BaseModel):
    query: str
    top_k: int
    mode: str = "hybrid_rrf"
    embedding_model: str
    results: list[RetrievalResult]
