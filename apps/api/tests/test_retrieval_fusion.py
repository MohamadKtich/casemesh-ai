from unittest.mock import Mock
from uuid import uuid4

from casemesh.db.models import DocumentChunk
from casemesh.repositories.retrieval import KeywordSearchHit, VectorSearchHit
from casemesh.services.retrieval import RetrievalService


def _chunk(index: int) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        document_id=uuid4(),
        case_id=uuid4(),
        chunk_index=index,
        content=f"chunk {index}",
        char_count=7,
        metadata_json={"chunk_index": index},
    )


def _service() -> RetrievalService:
    return RetrievalService(
        case_repository=Mock(),
        document_repository=Mock(),
        retrieval_repository=Mock(),
        embedding_provider=Mock(),
    )


def test_rrf_rewards_chunks_present_in_both_rankings() -> None:
    shared = _chunk(0)
    vector_only = _chunk(1)
    keyword_only = _chunk(2)

    results = _service()._fuse(
        vector_hits=[
            VectorSearchHit(shared, similarity=0.9),
            VectorSearchHit(vector_only, similarity=0.8),
        ],
        keyword_hits=[
            KeywordSearchHit(shared, rank_score=0.7),
            KeywordSearchHit(keyword_only, rank_score=0.6),
        ],
        top_k=3,
    )

    assert results[0].chunk_id == shared.id
    assert results[0].vector_rank == 1
    assert results[0].keyword_rank == 1


def test_rrf_respects_top_k() -> None:
    results = _service()._fuse(
        vector_hits=[
            VectorSearchHit(_chunk(0), similarity=0.9),
            VectorSearchHit(_chunk(1), similarity=0.8),
            VectorSearchHit(_chunk(2), similarity=0.7),
        ],
        keyword_hits=[],
        top_k=2,
    )

    assert len(results) == 2
