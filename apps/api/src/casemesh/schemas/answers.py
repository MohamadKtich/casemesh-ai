from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class GenerationHealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    model_available: bool
    detail: str | None = None


class GroundedAnswerRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=10)


class GroundedModelOutput(BaseModel):
    answer: str = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    abstained: bool = False


class EvidenceCitation(BaseModel):
    label: str
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    excerpt: str


class GroundingMetadata(BaseModel):
    retrieved_chunks: int
    context_chunks: int
    cited_chunks: int
    citation_source_ratio: float


class GroundedAnswerResponse(BaseModel):
    question: str
    answer: str
    confidence: Literal["low", "medium", "high"]
    abstained: bool
    citations: list[EvidenceCitation]
    grounding: GroundingMetadata
    retrieval_mode: str
    embedding_model: str
    generation_provider: str
    generation_model: str
