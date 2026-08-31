from uuid import uuid4

from casemesh.grounding.context import EvidenceContextBuilder
from casemesh.schemas.retrieval import RetrievalResult


def _result(content: str, index: int) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=index,
        content=content,
        metadata_json={"chunk_index": index},
        hybrid_score=0.1,
        vector_rank=index + 1,
        keyword_rank=None,
        vector_similarity=0.5,
        keyword_score=None,
    )


def test_context_builder_assigns_stable_labels() -> None:
    builder = EvidenceContextBuilder(
        max_context_chars=1000,
        max_source_chars=500,
    )

    sources = builder.build(
        [
            _result("first evidence", 0),
            _result("second evidence", 1),
        ]
    )

    assert [source.label for source in sources] == ["E1", "E2"]


def test_context_builder_enforces_source_limit() -> None:
    builder = EvidenceContextBuilder(
        max_context_chars=1000,
        max_source_chars=10,
    )

    sources = builder.build([_result("abcdefghijklmno", 0)])

    assert sources[0].content == "abcdefghij"
