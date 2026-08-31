import csv
import json
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from casemesh.core.exceptions import UnsupportedDocumentTypeError


class DocumentParser(Protocol):
    name: str

    def parse(self, path: Path) -> str:
        """Extract text from a document."""


class PlainTextParser:
    name = "plain-text"

    def parse(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")


class JsonParser:
    name = "json"

    def parse(self, path: Path) -> str:
        data = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(data, indent=2, ensure_ascii=False)


class CsvParser:
    name = "csv"

    def parse(self, path: Path) -> str:
        rows: list[str] = []
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            for row in reader:
                rows.append(" | ".join(cell.strip() for cell in row))
        return "\n".join(rows)


class PdfParser:
    name = "pypdf"

    def parse(self, path: Path) -> str:
        reader = PdfReader(str(path), strict=False)
        pages: list[str] = []

        for index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(f"[Page {index}]\n{page_text.strip()}")

        return "\n\n".join(pages)


def get_parser(path: Path) -> DocumentParser:
    extension = path.suffix.lower()

    if extension in {".txt", ".md"}:
        return PlainTextParser()
    if extension == ".json":
        return JsonParser()
    if extension == ".csv":
        return CsvParser()
    if extension == ".pdf":
        return PdfParser()

    raise UnsupportedDocumentTypeError(f"No parser available for '{extension}'.")
