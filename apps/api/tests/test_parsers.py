import json
from pathlib import Path

from casemesh.ingestion.parsers import CsvParser, JsonParser, PlainTextParser


def test_plain_text_parser(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("Case evidence", encoding="utf-8")

    assert PlainTextParser().parse(path) == "Case evidence"


def test_json_parser(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    path.write_text(json.dumps({"status": "open"}), encoding="utf-8")

    parsed = JsonParser().parse(path)
    assert '"status": "open"' in parsed


def test_csv_parser(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text("event,severity\noutage,high\n", encoding="utf-8")

    parsed = CsvParser().parse(path)
    assert "event | severity" in parsed
    assert "outage | high" in parsed
