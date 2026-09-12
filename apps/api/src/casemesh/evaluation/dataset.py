"""Dataset loading and exact benchmark duplicate detection."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from casemesh.evaluation.contracts import EvaluationCase


class DuplicateGroup(BaseModel):
    """One group of benchmark records with identical case content."""

    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(min_length=64, max_length=64)
    representative_id: str
    evaluation_ids: list[str]
    count: int = Field(ge=2)


class BenchmarkDataset(BaseModel):
    """Loaded benchmark plus exact-content deduplication metadata."""

    model_config = ConfigDict(extra="forbid")

    source_directory: str
    total_records: int = Field(ge=0)
    unique_records: int = Field(ge=0)
    duplicate_records: int = Field(ge=0)
    records: list[EvaluationCase]
    unique_cases: list[EvaluationCase]
    duplicate_groups: list[DuplicateGroup]


def case_fingerprint(case: EvaluationCase) -> str:
    """Hash benchmark content while intentionally ignoring evaluation_id."""

    payload = case.model_dump(
        mode="json",
        exclude={"evaluation_id"},
    )

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_evaluation_dataset(directory: Path) -> BenchmarkDataset:
    """Load, validate, and exactly deduplicate evaluation JSON records."""

    if not directory.exists():
        raise FileNotFoundError(f"Evaluation directory not found: {directory}")

    if not directory.is_dir():
        raise NotADirectoryError(f"Evaluation path is not a directory: {directory}")

    files = sorted(directory.glob("EVAL-*.json"))

    if not files:
        raise ValueError(f"No evaluation JSON files found in: {directory}")

    records: list[EvaluationCase] = []
    groups: dict[str, list[EvaluationCase]] = defaultdict(list)
    seen_ids: set[str] = set()

    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        case = EvaluationCase.model_validate(raw)

        if path.stem != case.evaluation_id:
            raise ValueError(
                "Evaluation filename does not match evaluation_id: "
                f"{path.name} != {case.evaluation_id}.json"
            )

        if case.evaluation_id in seen_ids:
            raise ValueError(
                f"Duplicate evaluation_id detected: {case.evaluation_id}"
            )

        seen_ids.add(case.evaluation_id)
        records.append(case)
        groups[case_fingerprint(case)].append(case)

    unique_cases = [
        grouped_cases[0]
        for grouped_cases in groups.values()
    ]

    duplicate_groups = [
        DuplicateGroup(
            fingerprint=fingerprint,
            representative_id=grouped_cases[0].evaluation_id,
            evaluation_ids=[
                case.evaluation_id
                for case in grouped_cases
            ],
            count=len(grouped_cases),
        )
        for fingerprint, grouped_cases in groups.items()
        if len(grouped_cases) > 1
    ]

    return BenchmarkDataset(
        source_directory=str(directory),
        total_records=len(records),
        unique_records=len(unique_cases),
        duplicate_records=len(records) - len(unique_cases),
        records=records,
        unique_cases=unique_cases,
        duplicate_groups=duplicate_groups,
    )
