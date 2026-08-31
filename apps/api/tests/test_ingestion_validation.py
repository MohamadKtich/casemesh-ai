import pytest

from casemesh.core.exceptions import UnsupportedDocumentTypeError
from casemesh.ingestion.validation import sanitize_filename, validate_document_extension


def test_sanitize_filename_removes_path_traversal() -> None:
    assert sanitize_filename("../../secret.txt") == "secret.txt"


def test_sanitize_filename_replaces_unsafe_characters() -> None:
    assert sanitize_filename("invoice<>:?.pdf") == "invoice_.pdf"


def test_validate_document_extension_accepts_pdf() -> None:
    assert validate_document_extension("evidence.PDF") == ".pdf"


def test_validate_document_extension_rejects_executable() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        validate_document_extension("payload.exe")
