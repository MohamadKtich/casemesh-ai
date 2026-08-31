import re
from pathlib import Path

from casemesh.core.exceptions import UnsupportedDocumentTypeError

ALLOWED_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".pdf"}
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")


def sanitize_filename(filename: str) -> str:
    basename = Path(filename).name.strip()
    cleaned = _SAFE_FILENAME_RE.sub("_", basename).strip(" .")

    if not cleaned:
        return "document"

    return cleaned[:240]


def validate_document_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        supported = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UnsupportedDocumentTypeError(
            f"Unsupported file type '{extension or 'none'}'. Supported: {supported}"
        )
    return extension
