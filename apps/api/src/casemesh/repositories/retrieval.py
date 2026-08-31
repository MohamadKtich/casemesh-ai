from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from casemesh.db.models import DocumentChunk


@dataclass(frozen=True)
class VectorSearchHit:
    chunk: DocumentChunk
    similarity: float


@dataclass(frozen=True)
class KeywordSearchHit:
    chunk: DocumentChunk
    rank_score: float


class RetrievalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store_embeddings(
        self,
        *,
        document_id: UUID,
        chunk_ids: list[UUID],
        embeddings: list[list[float]],
        model_name: str,
    ) -> int:
        if len(chunk_ids) != len(embeddings):
            raise ValueError("Chunk and embedding counts do not match.")

        result = await self._session.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.id.in_(chunk_ids),
            )
            .order_by(DocumentChunk.chunk_index.asc())
        )
        chunks = list(result.scalars().all())

        by_id = {chunk.id: chunk for chunk in chunks}
        embedded_at = datetime.now(UTC)

        for chunk_id, embedding in zip(chunk_ids, embeddings, strict=True):
            chunk = by_id.get(chunk_id)
            if chunk is None:
                raise ValueError(f"Chunk not found: {chunk_id}")

            chunk.embedding = embedding
            chunk.embedding_model = model_name
            chunk.embedded_at = embedded_at

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return len(chunk_ids)

    async def vector_search(
        self,
        *,
        case_id: UUID,
        query_embedding: list[float],
        limit: int,
    ) -> list[VectorSearchHit]:
        embedding_column = cast(Any, DocumentChunk.embedding)
        distance = embedding_column.cosine_distance(query_embedding).label("cosine_distance")

        result = await self._session.execute(
            select(DocumentChunk, distance)
            .where(
                DocumentChunk.case_id == case_id,
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance.asc())
            .limit(limit)
        )

        hits: list[VectorSearchHit] = []
        for chunk, raw_distance in result.all():
            distance_value = float(raw_distance)
            similarity = max(-1.0, min(1.0, 1.0 - distance_value))
            hits.append(
                VectorSearchHit(
                    chunk=chunk,
                    similarity=similarity,
                )
            )

        return hits

    async def keyword_search(
        self,
        *,
        case_id: UUID,
        query: str,
        limit: int,
    ) -> list[KeywordSearchHit]:
        document_vector = func.to_tsvector("english", DocumentChunk.content)
        query_vector = func.plainto_tsquery("english", query)
        rank_score = func.ts_rank_cd(document_vector, query_vector).label("rank_score")

        result = await self._session.execute(
            select(DocumentChunk, rank_score)
            .where(
                DocumentChunk.case_id == case_id,
                document_vector.op("@@")(query_vector),
            )
            .order_by(desc(rank_score))
            .limit(limit)
        )

        return [
            KeywordSearchHit(
                chunk=chunk,
                rank_score=float(raw_rank),
            )
            for chunk, raw_rank in result.all()
        ]
