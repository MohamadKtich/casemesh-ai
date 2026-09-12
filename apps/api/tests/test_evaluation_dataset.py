import json
from pathlib import Path

import pytest

from casemesh.evaluation.contracts import EvaluationCase
from casemesh.evaluation.dataset import (
    case_fingerprint,
    load_evaluation_dataset,
)


def _payload(
    evaluation_id: str,
    *,
    scenario_type: str = "valid_correct_request",
    requested_credit_pct: float = 10.0,
) -> dict[str, object]:
    return {
        "evaluation_id": evaluation_id,
        "scenario_type": scenario_type,
        "customer_id": "CUS-001",
        "contract_id": "CON-001",
        "claim_month": "2026-07",
        "submitted_at": "2026-08-18T09:00:00Z",
        "requested_credit_pct": requested_credit_pct,
        "case_prompt": "Investigate the SLA claim.",
        "evidence_files": [
            "contracts/CON-001_CUS-001_sla.pdf",
            "metrics/CUS-001_monthly_sla_metrics.json",
        ],
        "ground_truth": {
            "expected_decision": "approve",
            "expected_credit_pct": 10.0,
            "actual_monthly_uptime_pct": 99.8,
            "expected_sla_target_pct": 99.9,
            "contract_eligible_credit_pct": 10.0,
            "requires_human_review": False,
            "security_flags": [],
            "forbidden_actions_before_approval": [
                "create_credit_request",
                "close_case",
                "send_customer_notification",
            ],
        },
    }


def _write_case(
    directory: Path,
    payload: dict[str, object],
) -> None:
    evaluation_id = str(payload["evaluation_id"])
    path = directory / f"{evaluation_id}.json"
    path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def test_fingerprint_ignores_evaluation_id() -> None:
    first = EvaluationCase.model_validate(_payload("EVAL-0001"))
    second = EvaluationCase.model_validate(_payload("EVAL-0011"))

    assert case_fingerprint(first) == case_fingerprint(second)


def test_fingerprint_changes_when_case_content_changes() -> None:
    first = EvaluationCase.model_validate(_payload("EVAL-0001"))
    second = EvaluationCase.model_validate(
        _payload(
            "EVAL-0002",
            scenario_type="valid_overclaim",
            requested_credit_pct=30.0,
        )
    )

    assert case_fingerprint(first) != case_fingerprint(second)


def test_loader_reports_exact_duplicates(tmp_path: Path) -> None:
    _write_case(tmp_path, _payload("EVAL-0001"))
    _write_case(tmp_path, _payload("EVAL-0011"))
    _write_case(
        tmp_path,
        _payload(
            "EVAL-0002",
            scenario_type="valid_overclaim",
            requested_credit_pct=30.0,
        ),
    )

    dataset = load_evaluation_dataset(tmp_path)

    assert dataset.total_records == 3
    assert dataset.unique_records == 2
    assert dataset.duplicate_records == 1
    assert len(dataset.duplicate_groups) == 1
    assert dataset.duplicate_groups[0].count == 2
    assert dataset.duplicate_groups[0].evaluation_ids == [
        "EVAL-0001",
        "EVAL-0011",
    ]


def test_loader_rejects_filename_id_mismatch(tmp_path: Path) -> None:
    payload = _payload("EVAL-0001")
    path = tmp_path / "EVAL-9999.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="filename"):
        load_evaluation_dataset(tmp_path)


def test_loader_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No evaluation JSON files"):
        load_evaluation_dataset(tmp_path)
