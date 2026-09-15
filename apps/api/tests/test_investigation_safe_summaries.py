from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from casemesh.db.models import InvestigationRun
from casemesh.services.investigations import InvestigationService

CASE_ID = UUID("11111111-1111-1111-1111-111111111111")

RUN_ID = UUID("22222222-2222-2222-2222-222222222222")


def _run(
    metadata_json: object,
) -> InvestigationRun:
    now = datetime.now(UTC)

    run = SimpleNamespace(
        id=RUN_ID,
        case_id=CASE_ID,
        objective=("Synthetic investigation objective."),
        state="completed",
        current_step="completed",
        attempt=1,
        confidence="high",
        abstained=False,
        analysis_text=("Synthetic analysis."),
        assessment_text=("Synthetic assessment."),
        findings_text=("Synthetic finding."),
        plan_json=[],
        evidence_json=[],
        gaps_json=[],
        citations_json=[],
        metadata_json=metadata_json,
        error_message=None,
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )

    return cast(
        InvestigationRun,
        run,
    )


def test_legacy_investigation_metadata_has_null_safe_summaries() -> None:
    response = InvestigationService._to_response(_run({}))

    assert response.risk_triggers is None
    assert response.second_review is None


@pytest.mark.parametrize(
    (
        "metadata",
        "risk_is_none",
        "review_is_none",
    ),
    [
        (
            {
                "risk_triggers": "invalid",
                "second_review": [],
            },
            True,
            True,
        ),
        (
            {
                "risk_triggers": [],
                "second_review": "invalid",
            },
            True,
            True,
        ),
        (
            "invalid",
            True,
            True,
        ),
    ],
)
def test_malformed_metadata_fails_closed_to_null_summaries(
    metadata: object,
    risk_is_none: bool,
    review_is_none: bool,
) -> None:
    response = InvestigationService._to_response(_run(metadata))

    assert (response.risk_triggers is None) is risk_is_none

    assert (response.second_review is None) is review_is_none


def test_safe_summaries_filter_internal_metadata() -> None:
    response = InvestigationService._to_response(
        _run(
            {
                "risk_triggers": {
                    "request_second_review": True,
                    "reason_codes": [
                        "LOW_CONFIDENCE",
                        " LOW_CONFIDENCE ",
                        "",
                        7,
                        "MANUAL_SECOND_REVIEW_REQUEST",
                    ],
                    "triggers": [
                        {
                            "code": "LOW_CONFIDENCE",
                            "source": "investigation",
                            "rationale": "Internal rationale.",
                        }
                    ],
                },
                "second_review": {
                    "status": "completed",
                    "provider": "aws-bedrock",
                    "model": "internal-model",
                    "agreement": "disagree",
                    "risk_level": "high",
                    "concerns": ["Sensitive provider concern."],
                    "provider_route": "continue",
                    "effective_route": "human_review",
                    "forced_human_review": True,
                    "reason_codes": [
                        "review_disagreed",
                        " review_disagreed ",
                        "",
                        None,
                        "high_risk_review",
                    ],
                    "rationale": "Sensitive provider rationale.",
                    "error_type": "InternalProviderError",
                    "aws_boundary_failure": True,
                    "aws_boundary_component": "bedrock_review",
                    "alert_delivery": {
                        "provider": "aws-sns",
                        "message_id": "internal-message-id",
                    },
                    "reserved_attempts": 1,
                    "max_reviews": 1,
                    "guardrail_provider": "aws-bedrock-guardrails",
                    "guardrail_stage": "output",
                },
                "second_review_budget": {
                    "reserved_attempts": 1,
                    "max_reviews": 1,
                },
            }
        )
    )

    assert response.risk_triggers is not None
    assert response.second_review is not None

    assert response.risk_triggers.model_dump() == {
        "second_review_requested": True,
        "reason_codes": [
            "LOW_CONFIDENCE",
            "MANUAL_SECOND_REVIEW_REQUEST",
        ],
    }

    assert response.second_review.model_dump() == {
        "status": "completed",
        "agreement": "disagree",
        "risk_level": "high",
        "provider_route": "continue",
        "effective_route": "human_review",
        "forced_human_review": True,
        "reason_codes": [
            "review_disagreed",
            "high_risk_review",
        ],
        "guardrail_decision": None,
    }


def test_unknown_or_malformed_values_are_normalized_safely() -> None:
    response = InvestigationService._to_response(
        _run(
            {
                "risk_triggers": {
                    "request_second_review": "true",
                    "reason_codes": "LOW_CONFIDENCE",
                },
                "second_review": {
                    "status": "mystery_status",
                    "agreement": "maybe",
                    "risk_level": "extreme",
                    "provider_route": "auto_execute",
                    "effective_route": "auto_execute",
                    "forced_human_review": 1,
                    "reason_codes": {"unsafe": "shape"},
                },
            }
        )
    )

    assert response.risk_triggers is not None
    assert response.second_review is not None

    assert response.risk_triggers.second_review_requested is False
    assert response.risk_triggers.reason_codes == []

    assert response.second_review.model_dump() == {
        "status": None,
        "agreement": None,
        "risk_level": None,
        "provider_route": None,
        "effective_route": None,
        "forced_human_review": False,
        "reason_codes": [],
        "guardrail_decision": None,
    }


@pytest.mark.parametrize(
    (
        "status",
        "expected_decision",
    ),
    [
        (
            "guardrail_blocked",
            "blocked",
        ),
        (
            "guardrail_failed",
            "failed",
        ),
        (
            "completed",
            None,
        ),
    ],
)
def test_guardrail_decision_is_derived_only_from_safe_status(
    status: str,
    expected_decision: str | None,
) -> None:
    response = InvestigationService._to_response(
        _run(
            {
                "second_review": {
                    "status": status,
                    "guardrail_decision": "unsafe_raw_value",
                    "guardrail_provider": "hidden-provider",
                    "guardrail_stage": "output",
                }
            }
        )
    )

    assert response.second_review is not None
    assert response.second_review.guardrail_decision == expected_decision


def test_response_never_exposes_raw_metadata_container() -> None:
    response = InvestigationService._to_response(
        _run(
            {
                "provider": "top-level-provider",
                "metadata_json": {"should": "never leak"},
                "risk_triggers": {
                    "request_second_review": False,
                    "reason_codes": [],
                    "secret_internal_field": "hidden",
                },
                "second_review": {
                    "status": "failed",
                    "provider": "hidden-provider",
                    "model": "hidden-model",
                    "rationale": "hidden-rationale",
                    "concerns": ["hidden-concern"],
                    "error_type": "HiddenError",
                    "aws_boundary_failure": True,
                    "aws_boundary_component": "hidden-boundary",
                    "alert_delivery": {"message_id": "hidden-message"},
                    "reserved_attempts": 1,
                    "max_reviews": 1,
                    "guardrail_provider": "hidden-guardrail",
                    "guardrail_stage": "input",
                    "effective_route": "human_review",
                    "forced_human_review": True,
                    "reason_codes": ["provider_failure"],
                },
            }
        )
    )

    payload = response.model_dump(mode="json")

    assert "metadata_json" not in payload

    assert payload["risk_triggers"] == {
        "second_review_requested": False,
        "reason_codes": [],
    }

    assert payload["second_review"] == {
        "status": "failed",
        "agreement": None,
        "risk_level": None,
        "provider_route": None,
        "effective_route": "human_review",
        "forced_human_review": True,
        "reason_codes": ["provider_failure"],
        "guardrail_decision": None,
    }
