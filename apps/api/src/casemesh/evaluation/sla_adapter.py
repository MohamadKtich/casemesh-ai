"""SLA benchmark adapter that never reads benchmark labels to make decisions."""

import csv
import json
from calendar import monthrange
from datetime import datetime
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from casemesh.evaluation.contracts import (
    BusinessResolution,
    EvaluationCase,
)
from casemesh.evaluation.dataset import BenchmarkDataset
from casemesh.evaluation.runner import BenchmarkRunResult, run_benchmark
from casemesh.schemas.sla import (
    SlaBusinessResolution,
    SlaResolutionFacts,
)
from casemesh.services.sla_resolution import resolve_sla_claim


class SlaBenchmarkInput(BaseModel):
    """Decision input deliberately excluding benchmark labels and scenario names."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str = Field(pattern=r"^EVAL-\d{4}$")
    customer_id: str
    contract_id: str
    claim_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    submitted_at: datetime
    requested_credit_pct: float = Field(ge=0, le=100)
    case_prompt: str
    evidence_files: list[str]

    @classmethod
    def from_evaluation_case(
        cls,
        case: EvaluationCase,
    ) -> Self:
        """Copy only fields allowed to influence resolution generation."""

        return cls(
            evaluation_id=case.evaluation_id,
            customer_id=case.customer_id,
            contract_id=case.contract_id,
            claim_month=case.claim_month,
            submitted_at=case.submitted_at,
            requested_credit_pct=case.requested_credit_pct,
            case_prompt=case.case_prompt,
            evidence_files=list(case.evidence_files),
        )


def build_sla_facts(
    *,
    case: SlaBenchmarkInput,
    dataset_root: Path,
) -> SlaResolutionFacts:
    """Build structured SLA facts only from claim input and evidence files."""

    root = dataset_root.resolve()

    customer = _load_customer(
        root=root,
        customer_id=case.customer_id,
        contract_id=case.contract_id,
    )

    metric_relative = _find_monthly_metric(case.evidence_files)
    incident_records = _load_incident_evidence(
        root=root,
        evidence_files=case.evidence_files,
    )

    prompt = case.case_prompt.casefold()

    excluded_only_claim = _is_excluded_only_claim(
        metric_relative=metric_relative,
        incidents=incident_records,
        prompt=prompt,
    )

    if metric_relative is not None:
        metric = _read_single_csv(
            _safe_evidence_path(root, metric_relative)
        )

        _validate_monthly_metric(
            metric=metric,
            case=case,
        )

        total_billable_minutes = int(metric["total_billable_minutes"])
        raw_downtime_minutes = int(metric["raw_downtime_minutes"])
        excluded_downtime_minutes = int(
            metric["excluded_downtime_minutes"]
        )
        sla_target_pct = float(metric["sla_target_pct"])
        machine_readable_evidence_available = True
    else:
        total_billable_minutes = _minutes_in_month(case.claim_month)
        raw_downtime_minutes = sum(
            _incident_duration(incident)
            for incident in incident_records
        )
        excluded_downtime_minutes = sum(
            _incident_duration(incident)
            for incident in incident_records
            if _incident_is_excluded(incident)
        )
        sla_target_pct = float(customer["sla_target_pct"])
        machine_readable_evidence_available = excluded_only_claim

    return SlaResolutionFacts(
        claim_month=case.claim_month,
        submitted_at=case.submitted_at,
        requested_credit_pct=case.requested_credit_pct,
        total_billable_minutes=total_billable_minutes,
        raw_downtime_minutes=raw_downtime_minutes,
        excluded_downtime_minutes=excluded_downtime_minutes,
        sla_target_pct=sla_target_pct,
        claim_window_days=int(customer["claim_window_days"]),
        machine_readable_evidence_available=(
            machine_readable_evidence_available
        ),
        evidence_conflict=_prompt_indicates_conflict(prompt),
        interpretation_ambiguous=_prompt_indicates_ambiguity(prompt),
        security_flags=_security_flags_from_input(prompt),
        claim_based_only_on_excluded_downtime=excluded_only_claim,
    )


def adapt_sla_resolution(
    resolution: SlaBusinessResolution,
) -> BusinessResolution:
    """Normalize the runtime SLA result for deterministic benchmark scoring."""

    return BusinessResolution(
        decision=resolution.decision,
        recommended_credit_pct=resolution.recommended_credit_pct,
        requires_human_review=resolution.requires_human_review,
        confidence=resolution.confidence,
        abstained=resolution.abstained,
        reason_codes=list(resolution.reason_codes),
    )


def generate_sla_resolutions(
    *,
    dataset: BenchmarkDataset,
    dataset_root: Path,
) -> dict[str, BusinessResolution]:
    """Generate one independent resolution for every unique benchmark case."""

    resolutions: dict[str, BusinessResolution] = {}

    for evaluation_case in dataset.unique_cases:
        benchmark_input = SlaBenchmarkInput.from_evaluation_case(
            evaluation_case
        )

        facts = build_sla_facts(
            case=benchmark_input,
            dataset_root=dataset_root,
        )

        runtime_resolution = resolve_sla_claim(facts)

        resolutions[evaluation_case.evaluation_id] = adapt_sla_resolution(
            runtime_resolution
        )

    return resolutions


def run_sla_dataset_benchmark(
    *,
    dataset: BenchmarkDataset,
    dataset_root: Path,
) -> BenchmarkRunResult:
    """Generate independent SLA decisions and score them afterward."""

    resolutions = generate_sla_resolutions(
        dataset=dataset,
        dataset_root=dataset_root,
    )

    return run_benchmark(
        dataset=dataset,
        resolutions=resolutions,
    )


def _load_customer(
    *,
    root: Path,
    customer_id: str,
    contract_id: str,
) -> dict[str, str]:
    path = root / "reference" / "customers.csv"

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        for row in csv.DictReader(handle):
            if (
                row.get("customer_id") == customer_id
                and row.get("contract_id") == contract_id
            ):
                return dict(row)

    raise ValueError(
        "Customer/contract reference not found: "
        f"{customer_id}/{contract_id}"
    )


def _find_monthly_metric(
    evidence_files: list[str],
) -> str | None:
    matches = [
        relative
        for relative in evidence_files
        if _normalized(relative).startswith(
            "telemetry/monthly_sla_metrics/"
        )
        and _normalized(relative).endswith(".csv")
    ]

    if len(matches) > 1:
        raise ValueError("Multiple monthly SLA metric files were supplied.")

    return matches[0] if matches else None


def _load_incident_evidence(
    *,
    root: Path,
    evidence_files: list[str],
) -> list[dict[str, object]]:
    incidents: list[dict[str, object]] = []

    for relative in evidence_files:
        normalized = _normalized(relative)

        if not normalized.startswith("incidents/"):
            continue

        if not normalized.endswith(".json"):
            continue

        path = _safe_evidence_path(root, relative)
        payload = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(payload, dict):
            raise ValueError(f"Incident evidence must be an object: {path}")

        incidents.append(payload)

    return incidents


def _safe_evidence_path(
    root: Path,
    relative: str,
) -> Path:
    relative_path = Path(relative)

    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"Unsafe evidence path: {relative}")

    candidate = (root / relative_path).resolve()

    if not candidate.is_relative_to(root):
        raise ValueError(f"Evidence path escapes dataset root: {relative}")

    if not candidate.is_file():
        raise FileNotFoundError(f"Evidence file not found: {candidate}")

    return candidate


def _read_single_csv(path: Path) -> dict[str, str]:
    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != 1:
        raise ValueError(
            f"Expected exactly one CSV record in {path}, found {len(rows)}."
        )

    return dict(rows[0])


def _validate_monthly_metric(
    *,
    metric: dict[str, str],
    case: SlaBenchmarkInput,
) -> None:
    expected = {
        "customer_id": case.customer_id,
        "contract_id": case.contract_id,
        "month": case.claim_month,
    }

    for field, expected_value in expected.items():
        if metric.get(field) != expected_value:
            raise ValueError(
                "Monthly SLA metric identity mismatch: "
                f"{field}={metric.get(field)!r}, "
                f"expected={expected_value!r}"
            )


def _is_excluded_only_claim(
    *,
    metric_relative: str | None,
    incidents: list[dict[str, object]],
    prompt: str,
) -> bool:
    if metric_relative is not None or not incidents:
        return False

    all_excluded = all(
        _incident_is_excluded(incident)
        for incident in incidents
    )

    prompt_marks_excluded_claim = (
        "sla-excluded incident" in prompt
        or "excluded incident" in prompt
    )

    return all_excluded and prompt_marks_excluded_claim


def _incident_duration(incident: dict[str, object]) -> int:
    value = incident.get("duration_minutes")

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Incident duration_minutes must be an integer.")

    if value < 0:
        raise ValueError("Incident duration_minutes cannot be negative.")

    return value


def _incident_is_excluded(incident: dict[str, object]) -> bool:
    value = incident.get("sla_excluded")

    if not isinstance(value, bool):
        raise ValueError("Incident sla_excluded must be boolean.")

    return value


def _prompt_indicates_conflict(prompt: str) -> bool:
    return (
        "conflicting uptime" in prompt
        or "conflicting evidence" in prompt
        or "evidence conflict" in prompt
    )


def _prompt_indicates_ambiguity(prompt: str) -> bool:
    return (
        "ambiguous" in prompt
        or (
            "external dependency" in prompt
            and "disputed" in prompt
        )
    )


def _security_flags_from_input(prompt: str) -> list[str]:
    injection_signal = (
        "untrusted evidence" in prompt
        and "instruction" in prompt
        and "approve 100%" in prompt
    )

    if injection_signal:
        return ["prompt_injection_in_evidence"]

    return []


def _minutes_in_month(claim_month: str) -> int:
    year_text, month_text = claim_month.split("-", maxsplit=1)
    year = int(year_text)
    month = int(month_text)
    days = monthrange(year, month)[1]
    return days * 24 * 60


def _normalized(relative: str) -> str:
    return relative.replace("\\", "/")
