from pathlib import Path

from fastapi.testclient import TestClient

from casemesh.api.routes.evaluation import get_evaluation_reader
from casemesh.main import app
from casemesh.services.evaluation_artifacts import (
    EvaluationArtifactReader,
)

client = TestClient(app)


def test_evaluation_summary_endpoint() -> None:
    response = client.get("/evaluation/summary")

    assert response.status_code == 200

    body = response.json()

    assert body["run_id"] == "sla-deterministic-dataset-v1"
    assert body["dataset"]["total_records"] == 100
    assert body["dataset"]["unique_records"] == 10
    assert body["dataset"]["duplicate_records"] == 90
    assert body["evaluated_cases"] == 10
    assert body["failed_cases"] == 0
    assert body["metrics"]["decision_accuracy"] == 1.0
    assert body["metrics"]["credit_accuracy"] == 1.0
    assert body["metrics"]["human_review_accuracy"] == 1.0


def test_evaluation_stability_endpoint() -> None:
    response = client.get("/evaluation/stability")

    assert response.status_code == 200

    body = response.json()

    assert body["repeated_runs"] == 20
    assert body["unique_scenarios_per_run"] == 10
    assert body["total_case_executions"] == 200
    assert body["unique_result_hashes"] == 1
    assert body["decision_stability"] == 1.0
    assert body["credit_stability"] == 1.0
    assert body["human_review_stability"] == 1.0
    assert body["stable"] is True
    assert body["timing_scope"] == "local_diagnostic_only"


def test_evaluation_cases_endpoint_returns_unique_cases() -> None:
    response = client.get("/evaluation/cases")

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 10
    assert len({case["evaluation_id"] for case in body}) == 10
    assert len({case["fingerprint"] for case in body}) == 10

    for case in body:
        assert case["score"]["decision_correct"] is True
        assert case["score"]["human_review_correct"] is True


def test_evaluation_failures_endpoint() -> None:
    response = client.get("/evaluation/failures")

    assert response.status_code == 200

    body = response.json()

    assert body["run_id"] == "sla-deterministic-dataset-v1"
    assert body["failed_cases"] == 0
    assert body["cases"] == []


def test_evaluation_routes_are_in_openapi() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/evaluation/summary" in paths
    assert "/evaluation/stability" in paths
    assert "/evaluation/cases" in paths
    assert "/evaluation/failures" in paths

    assert "get" in paths["/evaluation/summary"]
    assert "get" in paths["/evaluation/stability"]
    assert "get" in paths["/evaluation/cases"]
    assert "get" in paths["/evaluation/failures"]


def test_evaluation_api_returns_503_when_artifacts_missing(
    tmp_path: Path,
) -> None:
    def missing_reader() -> EvaluationArtifactReader:
        return EvaluationArtifactReader(tmp_path)

    app.dependency_overrides[get_evaluation_reader] = missing_reader

    try:
        response = client.get("/evaluation/summary")
    finally:
        app.dependency_overrides.pop(
            get_evaluation_reader,
            None,
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Evaluation artifacts are unavailable or failed "
            "integrity validation."
        )
    }
