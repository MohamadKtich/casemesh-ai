from dataclasses import dataclass
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from casemesh.core.config import get_settings
from casemesh.embeddings.base import EmbeddingProvider
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.documents import DocumentRepository
from casemesh.repositories.retrieval import (
    KeywordSearchHit,
    RetrievalRepository,
    VectorSearchHit,
)
from casemesh.schemas.retrieval import (
    DocumentEmbeddingResponse,
    RetrievalResult,
    RetrievalSearchResponse,
)

settings = get_settings()


@dataclass
class _FusionState:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    metadata_json: dict[str, object]
    hybrid_score: float = 0.0
    vector_rank: int | None = None
    keyword_rank: int | None = None
    vector_similarity: float | None = None
    keyword_score: float | None = None


class RetrievalService:
    def __init__(
        self,
        *,
        case_repository: CaseRepository,
        document_repository: DocumentRepository,
        retrieval_repository: RetrievalRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._cases = case_repository
        self._documents = document_repository
        self._retrieval = retrieval_repository
        self._embeddings = embedding_provider

    async def embedding_health(self) -> dict[str, object]:
        return await self._embeddings.health()

    async def _require_case(self, case_id: UUID) -> None:
        case = await self._cases.get(case_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found",
            )

    async def embed_document(
        self,
        *,
        case_id: UUID,
        document_id: UUID,
    ) -> DocumentEmbeddingResponse:
        await self._require_case(case_id)

        document = await self._documents.get_for_case(case_id, document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        if document.ingestion_status != "ready":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document must be ingested and ready before embedding.",
            )

        chunks = await self._documents.list_chunks(document_id)
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document has no chunks to embed.",
            )

        try:
            embeddings = await self._embeddings.embed_texts([chunk.content for chunk in chunks])
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Embedding provider is unavailable.",
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        for embedding in embeddings:
            if len(embedding) != settings.embedding_dimension:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Embedding dimension does not match database schema.",
                )

        chunks_embedded = await self._retrieval.store_embeddings(
            document_id=document_id,
            chunk_ids=[chunk.id for chunk in chunks],
            embeddings=embeddings,
            model_name=self._embeddings.model_name,
        )

        return DocumentEmbeddingResponse(
            case_id=case_id,
            document_id=document_id,
            provider=settings.embedding_provider,
            model=self._embeddings.model_name,
            dimension=self._embeddings.dimension,
            chunks_embedded=chunks_embedded,
        )

    async def search(
        self,
        *,
        case_id: UUID,
        query: str,
        top_k: int,
    ) -> RetrievalSearchResponse:
        await self._require_case(case_id)

        try:
            query_embeddings = await self._embeddings.embed_texts([query])
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Embedding provider is unavailable.",
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        if len(query_embeddings) != 1:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding provider returned an invalid query embedding.",
            )

        candidate_limit = max(top_k, settings.retrieval_candidate_limit)

        vector_hits = await self._retrieval.vector_search(
            case_id=case_id,
            query_embedding=query_embeddings[0],
            limit=candidate_limit,
        )
        keyword_hits = await self._retrieval.keyword_search(
            case_id=case_id,
            query=query,
            limit=candidate_limit,
        )

        results = self._fuse(
            vector_hits=vector_hits,
            keyword_hits=keyword_hits,
            top_k=top_k,
        )

        return RetrievalSearchResponse(
            query=query,
            top_k=top_k,
            embedding_model=self._embeddings.model_name,
            results=results,
        )

    def _fuse(
        self,
        *,
        vector_hits: list[VectorSearchHit],
        keyword_hits: list[KeywordSearchHit],
        top_k: int,
    ) -> list[RetrievalResult]:
        states: dict[UUID, _FusionState] = {}
        rrf_k = settings.retrieval_rrf_k

        for rank, vector_hit in enumerate(vector_hits, start=1):
            state = states.setdefault(
                vector_hit.chunk.id,
                _FusionState(
                    chunk_id=vector_hit.chunk.id,
                    document_id=vector_hit.chunk.document_id,
                    chunk_index=vector_hit.chunk.chunk_index,
                    content=vector_hit.chunk.content,
                    metadata_json=vector_hit.chunk.metadata_json,
                ),
            )
            state.vector_rank = rank
            state.vector_similarity = vector_hit.similarity
            state.hybrid_score += settings.retrieval_vector_weight / (rrf_k + rank)

        for rank, keyword_hit in enumerate(keyword_hits, start=1):
            state = states.setdefault(
                keyword_hit.chunk.id,
                _FusionState(
                    chunk_id=keyword_hit.chunk.id,
                    document_id=keyword_hit.chunk.document_id,
                    chunk_index=keyword_hit.chunk.chunk_index,
                    content=keyword_hit.chunk.content,
                    metadata_json=keyword_hit.chunk.metadata_json,
                ),
            )
            state.keyword_rank = rank
            state.keyword_score = keyword_hit.rank_score
            state.hybrid_score += settings.retrieval_keyword_weight / (rrf_k + rank)

        ranked_states = sorted(
            states.values(),
            key=lambda state: state.hybrid_score,
            reverse=True,
        )[:top_k]

        return [
            RetrievalResult(
                chunk_id=state.chunk_id,
                document_id=state.document_id,
                chunk_index=state.chunk_index,
                content=state.content,
                metadata_json=state.metadata_json,
                hybrid_score=round(state.hybrid_score, 8),
                vector_rank=state.vector_rank,
                keyword_rank=state.keyword_rank,
                vector_similarity=state.vector_similarity,
                keyword_score=state.keyword_score,
            )
            for state in ranked_states
        ]
