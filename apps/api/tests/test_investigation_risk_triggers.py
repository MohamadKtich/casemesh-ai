from types import SimpleNamespace
from uuid import UUID

import pytest

from casemesh.api.routes.investigations import (
    start_investigation,
)
from casemesh.core.config import Settings
from casemesh.schemas.investigations import (
    InvestigationStartRequest,
)
from casemesh.workflows.investigation import (
    InvestigationWorkflow,
    choose_post_findings_step,
)
from casemesh.workflows.state import (
    InvestigationState,
)

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")

RUN_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakeInvestigationRepository:
    def __init__(self) -> None:
        self.saved = 0

    async def save(
        self,
        run: object,
    ) -> object:
        self.saved += 1
        return run


class FakeInvestigationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

        self.response = object()

    async def start(
        self,
        *,
        case_id: UUID,
        objective: str,
        manual_second_review_requested: bool = False,
    ) -> object:
        self.calls.append(
            {
                "case_id": case_id,
                "objective": objective,
                "manual_second_review_requested": (manual_second_review_requested),
            }
        )

        return self.response


def _state(
    *,
    confidence: str = "high",
    abstained: bool = False,
    gaps: list[dict[str, object]] | None = None,
    manual: bool = False,
    evidence_conflict: bool = False,
    prompt_injection_signal: bool = False,
    security_flags: list[str] | None = None,
) -> InvestigationState:
    return {
        "workflow_id": RUN_ID,
        "case_id": CASE_ID,
        "objective": "Synthetic investigation objective.",
        "findings": "Synthetic supported finding.",
        "findings_confidence": confidence,
        "findings_abstained": abstained,
        "citations": [],
        "gaps": (
            gaps
            if gaps is not None
            else [
                {
                    "code": "NO_MATERIAL_GAP_DETECTED",
                    "description": ("Synthetic no-material-gap marker."),
                }
            ]
        ),
        "manual_second_review_requested": manual,
        "evidence_conflict": evidence_conflict,
        "prompt_injection_signal": (prompt_injection_signal),
        "security_flags": (security_flags if security_flags is not None else []),
        "second_review_requested": False,
    }


def _workflow() -> tuple[
    InvestigationWorkflow,
    SimpleNamespace,
    FakeInvestigationRepository,
]:
    run = SimpleNamespace(
        id=RUN_ID,
        current_step="produce_findings",
        metadata_json={
            "existing_metadata": "preserved",
        },
    )

    repository = FakeInvestigationRepository()

    workflow = InvestigationWorkflow(
        run=run,
        settings=Settings(
            _env_file=None,
            aws_bedrock_review_enabled=False,
        ),
        case_reader=object(),
        investigation_repository=repository,
        retrieval_service=object(),
        answer_service=object(),
        second_review_provider=None,
    )

    return (
        workflow,
        run,
        repository,
    )


def _trigger_codes(
    update: InvestigationState,
) -> list[str]:
    raw = update.get(
        "risk_trigger_codes",
        [],
    )

    return list(raw)


@pytest.mark.asyncio
async def test_high_confidence_without_risk_routes_to_finalize() -> None:
    workflow, run, repository = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            confidence="high",
        )
    )

    assert update["second_review_requested"] is False

    assert _trigger_codes(update) == []

    assert choose_post_findings_step(update) == "finalize"

    assert run.current_step == ("evaluate_risk_triggers")

    assert repository.saved == 1

    assert run.metadata_json["existing_metadata"] == "preserved"

    trigger_metadata = run.metadata_json["risk_triggers"]

    assert trigger_metadata["request_second_review"] is False

    assert trigger_metadata["reason_codes"] == []


@pytest.mark.asyncio
async def test_medium_confidence_without_risk_routes_to_finalize() -> None:
    workflow, _, _ = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            confidence="medium",
        )
    )

    assert update["second_review_requested"] is False

    assert _trigger_codes(update) == []

    assert choose_post_findings_step(update) == "finalize"


@pytest.mark.asyncio
async def test_low_confidence_routes_to_second_review() -> None:
    workflow, run, repository = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            confidence="low",
        )
    )

    assert update["second_review_requested"] is True

    assert _trigger_codes(update) == [
        "LOW_CONFIDENCE",
    ]

    assert choose_post_findings_step(update) == "second_review"

    metadata = run.metadata_json["risk_triggers"]

    assert metadata["reason_codes"] == [
        "LOW_CONFIDENCE",
    ]

    triggers = metadata["triggers"]

    assert isinstance(
        triggers,
        list,
    )

    assert triggers[0]["code"] == "LOW_CONFIDENCE"

    assert triggers[0]["source"] == "investigation"

    assert repository.saved == 1


@pytest.mark.asyncio
async def test_low_confidence_gap_triggers_even_with_high_finding() -> None:
    workflow, _, _ = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            confidence="high",
            gaps=[
                {
                    "code": "LOW_CONFIDENCE",
                    "description": ("Synthetic retained low-confidence gap."),
                }
            ],
        )
    )

    assert _trigger_codes(update) == [
        "LOW_CONFIDENCE",
    ]

    assert update["second_review_requested"] is True


@pytest.mark.asyncio
async def test_manual_request_routes_to_second_review() -> None:
    workflow, run, _ = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            confidence="high",
            manual=True,
        )
    )

    assert _trigger_codes(update) == [
        "MANUAL_SECOND_REVIEW_REQUEST",
    ]

    assert update["second_review_requested"] is True

    assert choose_post_findings_step(update) == "second_review"

    assert run.metadata_json["risk_triggers"]["request_second_review"] is True


@pytest.mark.asyncio
async def test_conflict_signal_slot_routes_to_second_review() -> None:
    workflow, _, _ = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            evidence_conflict=True,
        )
    )

    assert _trigger_codes(update) == [
        "CONFLICTING_EVIDENCE",
    ]

    assert choose_post_findings_step(update) == "second_review"


@pytest.mark.asyncio
async def test_conflict_gap_slot_routes_to_second_review() -> None:
    workflow, _, _ = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            gaps=[
                {
                    "code": "CONFLICTING_EVIDENCE",
                    "description": ("Synthetic evidence conflict."),
                }
            ],
        )
    )

    assert _trigger_codes(update) == [
        "CONFLICTING_EVIDENCE",
    ]


@pytest.mark.asyncio
async def test_prompt_injection_signal_routes_to_second_review() -> None:
    workflow, _, _ = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            prompt_injection_signal=True,
        )
    )

    assert _trigger_codes(update) == [
        "PROMPT_INJECTION_SIGNAL",
    ]

    assert choose_post_findings_step(update) == "second_review"


@pytest.mark.asyncio
async def test_existing_security_flag_routes_to_second_review() -> None:
    workflow, _, _ = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            security_flags=[
                "prompt_injection_in_evidence",
            ],
        )
    )

    assert _trigger_codes(update) == [
        "PROMPT_INJECTION_SIGNAL",
    ]


@pytest.mark.asyncio
async def test_investigation_trigger_order_is_deterministic() -> None:
    workflow, _, _ = _workflow()

    update = await workflow._evaluate_risk_triggers(
        _state(
            confidence="low",
            evidence_conflict=True,
            prompt_injection_signal=True,
            manual=True,
        )
    )

    assert _trigger_codes(update) == [
        "LOW_CONFIDENCE",
        "CONFLICTING_EVIDENCE",
        "PROMPT_INJECTION_SIGNAL",
        "MANUAL_SECOND_REVIEW_REQUEST",
    ]

    assert "HIGH_RISK_ACTION" not in _trigger_codes(update)

    assert "FINANCIAL_ACTION" not in _trigger_codes(update)


def test_manual_second_review_schema_defaults_false() -> None:
    payload = InvestigationStartRequest(objective="Synthetic investigation objective.")

    assert payload.manual_second_review_requested is False


def test_manual_second_review_schema_accepts_true() -> None:
    payload = InvestigationStartRequest(
        objective="Synthetic investigation objective.",
        manual_second_review_requested=True,
    )

    assert payload.manual_second_review_requested is True


@pytest.mark.asyncio
async def test_route_forwards_manual_second_review_request() -> None:
    service = FakeInvestigationService()

    payload = InvestigationStartRequest(
        objective="Synthetic investigation objective.",
        manual_second_review_requested=True,
    )

    result = await start_investigation(
        case_id=CASE_ID,
        payload=payload,
        service=service,
    )

    assert result is service.response

    assert service.calls == [
        {
            "case_id": CASE_ID,
            "objective": ("Synthetic investigation objective."),
            "manual_second_review_requested": True,
        }
    ]
