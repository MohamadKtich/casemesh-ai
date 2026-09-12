from pathlib import Path

REQUIRED_ARTIFACTS = {
    "evaluation_results.json",
    "evaluation_summary.json",
    "evaluation_failures.json",
    "evaluation_runs.csv",
    "evaluation_stability.json",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_canonical_evaluation_artifacts_exist() -> None:
    root = (
        _repo_root()
        / "data"
        / "evaluation"
        / "baseline-sla-v1"
    )

    assert root.is_dir()
    assert {
        path.name
        for path in root.iterdir()
        if path.is_file()
    } >= REQUIRED_ARTIFACTS


def test_api_dockerfile_packages_evaluation_artifacts() -> None:
    dockerfile = (
        _repo_root()
        / "apps"
        / "api"
        / "Dockerfile"
    ).read_text(encoding="utf-8")

    assert (
        "EVALUATION_ARTIFACT_ROOT="
        "/app/data/evaluation/baseline-sla-v1"
        in dockerfile
    )
    assert (
        "COPY data/evaluation/baseline-sla-v1 "
        "./data/evaluation/baseline-sla-v1"
        in dockerfile
    )

    for name in REQUIRED_ARTIFACTS:
        assert f"/baseline-sla-v1/{name}" in dockerfile


def test_api_deploy_uses_repository_root_context() -> None:
    workflow = (
        _repo_root()
        / ".github"
        / "workflows"
        / "api-deploy-dev.yml"
    ).read_text(encoding="utf-8")

    assert "context: ." in workflow
    assert "file: ./apps/api/Dockerfile" in workflow
    assert "context: ./apps/api" not in workflow


def test_root_dockerignore_allows_only_required_api_inputs() -> None:
    dockerignore = (
        _repo_root() / ".dockerignore"
    ).read_text(encoding="utf-8")

    assert "**" in dockerignore
    assert "!apps/api/pyproject.toml" in dockerignore
    assert "!apps/api/src/**" in dockerignore
    assert (
        "!data/evaluation/baseline-sla-v1/**"
        in dockerignore
    )
