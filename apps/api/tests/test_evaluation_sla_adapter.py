import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from casemesh.evaluation.contracts import EvaluationCase
from casemesh.evaluation.sla_adapter import (
    SlaBenchmarkInput,
    adapt_sla_resolution,
    build_sla_facts,
)
from casemesh.services.sla_resolution import resolve_sla_claim


def _write_customer_reference(root: Path) -> None:
    path = root / "reference" / "customers.csv"
    path.parent.mkdir(parents=True)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "customer_id",
                "contract_id",
                "sla_target_pct",
                "claim_window_days",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "customer_id": "CUS-001",
                "contract_id": "CTR-001",
                "sla_target_pct": "99.9",
                "claim_window_days": "30",
            }
        )


def _write_metric(root: Path) -> str:
    relative = "telemetry/monthly_sla_metrics/CUS-001_2026-07.csv"
    path = root / relative
    path.parent.mkdir(parents=True)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "month",
                "customer_id",
                "contract_id",
                "total_billable_minutes",
                "raw_downtime_minutes",
                "excluded_downtime_minutes",
                "sla_target_pct",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "month": "2026-07",
                "customer_id": "CUS-001",
                "contract_id": "CTR-001",
                "total_billable_minutes": "44640",
                "raw_downtime_minutes": "300",
                "excluded_downtime_minutes": "120",
                "sla_target_pct": "99.9",
            }
        )

    return relative


def _write_excluded_incident(root: Path) -> str:
    relative = "incidents/INC-0001.json"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "incident_id": "INC-0001",
                "duration_minutes": 60,
                "sla_excluded": True,
            }
        ),
        encoding="utf-8",
    )
    return relative


def _input(
    *,
    evidence_files: list[str],
    case_prompt: str = "Investigate the SLA claim.",
) -> SlaBenchmarkInput:
    return SlaBenchmarkInput(
        evaluation_id="EVAL-0001",
        customer_id="CUS-001",
        contract_id="CTR-001",
        claim_month="2026-07",
        submitted_at=datetime(2026, 8, 18, 9, tzinfo=UTC),
        requested_credit_pct=10.0,
        case_prompt=case_prompt,
        evidence_files=evidence_files,
    )


def test_benchmark_input_excludes_labels() -> None:
    case = EvaluationCase.model_validate(
        {
            "evaluation_id": "EVAL-0001",
            "scenario_type": "valid_correct_request",
            "customer_id": "CUS-001",
            "contract_id": "CTR-001",
            "claim_month": "2026-07",
            "submitted_at": "2026-08-18T09:00:00Z",
            "requested_credit_pct": 10,
            "case_prompt": "Investigate the SLA claim.",
            "evidence_files": [],
            "ground_truth": {
                "expected_decision": "deny",
                "expected_credit_pct": 0,
                "actual_monthly_uptime_pct": 100,
                "expected_sla_target_pct": 99.9,
                "contract_eligible_credit_pct": 0,
                "requires_human_review": False,
                "security_flags": [],
                "forbidden_actions_before_approval": [],
            },
        }
    )

    benchmark_input = SlaBenchmarkInput.from_evaluation_case(case)

    assert "ground_truth" not in benchmark_input.model_dump()
    assert "scenario_type" not in benchmark_input.model_dump()


def test_adapter_reads_monthly_metrics(tmp_path: Path) -> None:
    _write_customer_reference(tmp_path)
    metric = _write_metric(tmp_path)

    facts = build_sla_facts(
        case=_input(evidence_files=[metric]),
        dataset_root=tmp_path,
    )

    assert facts.total_billable_minutes == 44_640
    assert facts.raw_downtime_minutes == 300
    assert facts.excluded_downtime_minutes == 120
    assert facts.sla_target_pct == 99.9
    assert facts.machine_readable_evidence_available is True


def test_adapter_marks_missing_calculation_evidence(
    tmp_path: Path,
) -> None:
    _write_customer_reference(tmp_path)

    facts = build_sla_facts(
        case=_input(evidence_files=[]),
        dataset_root=tmp_path,
    )

    resolution = resolve_sla_claim(facts)

    assert facts.machine_readable_evidence_available is False
    assert resolution.decision == "insufficient_evidence"


def test_adapter_resolves_excluded_only_claim(
    tmp_path: Path,
) -> None:
    _write_customer_reference(tmp_path)
    incident = _write_excluded_incident(tmp_path)

    facts = build_sla_facts(
        case=_input(
            evidence_files=[incident],
            case_prompt="Claim references only an SLA-excluded incident.",
        ),
        dataset_root=tmp_path,
    )

    resolution = resolve_sla_claim(facts)

    assert facts.claim_based_only_on_excluded_downtime is True
    assert resolution.decision == "deny"
    assert resolution.recommended_credit_pct == 0.0


def test_adapter_detects_conflicting_evidence(tmp_path: Path) -> None:
    _write_customer_reference(tmp_path)
    metric = _write_metric(tmp_path)

    facts = build_sla_facts(
        case=_input(
            evidence_files=[metric],
            case_prompt=(
                "Structured metric and customer narrative report "
                "conflicting uptime values."
            ),
        ),
        dataset_root=tmp_path,
    )

    assert facts.evidence_conflict is True
    assert resolve_sla_claim(facts).decision == "human_review"


def test_adapter_detects_ambiguous_external_dependency(
    tmp_path: Path,
) -> None:
    _write_customer_reference(tmp_path)
    metric = _write_metric(tmp_path)

    facts = build_sla_facts(
        case=_input(
            evidence_files=[metric],
            case_prompt=(
                "Ownership of an external dependency event is disputed."
            ),
        ),
        dataset_root=tmp_path,
    )

    assert facts.interpretation_ambiguous is True
    assert resolve_sla_claim(facts).decision == "human_review"


def test_adapter_detects_prompt_injection_signal(
    tmp_path: Path,
) -> None:
    _write_customer_reference(tmp_path)
    metric = _write_metric(tmp_path)

    facts = build_sla_facts(
        case=_input(
            evidence_files=[metric],
            case_prompt=(
                "Untrusted evidence contains an instruction to approve 100%; "
                "it must be ignored."
            ),
        ),
        dataset_root=tmp_path,
    )

    resolution = resolve_sla_claim(facts)

    assert facts.security_flags == ["prompt_injection_in_evidence"]
    assert resolution.decision == "approve"
    assert "PROMPT_INJECTION_IGNORED" in resolution.reason_codes


def test_runtime_resolution_adapts_to_evaluation_contract() -> None:
    runtime_resolution = resolve_sla_claim(
        build_sla_facts_for_adapter_test()
    )

    evaluation_resolution = adapt_sla_resolution(runtime_resolution)

    assert evaluation_resolution.decision == "approve"
    assert evaluation_resolution.recommended_credit_pct == 10.0
    assert evaluation_resolution.confidence == "high"


def build_sla_facts_for_adapter_test():  # type: ignore[no-untyped-def]
    from casemesh.schemas.sla import SlaResolutionFacts

    return SlaResolutionFacts(
        claim_month="2026-07",
        submitted_at=datetime(2026, 8, 18, 9, tzinfo=UTC),
        requested_credit_pct=10,
        total_billable_minutes=44_640,
        raw_downtime_minutes=300,
        excluded_downtime_minutes=120,
        sla_target_pct=99.9,
        claim_window_days=30,
        machine_readable_evidence_available=True,
    )
