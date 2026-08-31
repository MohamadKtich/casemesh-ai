import pytest

from casemesh.ingestion.chunking import chunk_text


def test_chunk_text_returns_empty_for_blank_text() -> None:
    assert chunk_text("   \n\n") == []


def test_chunk_text_splits_long_text_with_overlap() -> None:
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text(text, max_chars=250, overlap_chars=50)

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 250 for chunk in chunks)


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_text("hello", max_chars=100, overlap_chars=100)
