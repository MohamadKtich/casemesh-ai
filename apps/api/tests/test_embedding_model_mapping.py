from pgvector.sqlalchemy import Vector

from casemesh.db.models import DocumentChunk


def test_document_chunk_embedding_is_768_dimension_vector() -> None:
    column_type = DocumentChunk.__table__.c.embedding.type

    assert isinstance(column_type, Vector)
    assert column_type.dim == 768


def test_embedding_metadata_columns_exist() -> None:
    columns = DocumentChunk.__table__.c

    assert "embedding_model" in columns
    assert "embedded_at" in columns
