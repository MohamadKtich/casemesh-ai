import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "aws-oidc-validate.yml"

CONFIGURE_AWS_CREDENTIALS_SHA = "cbe3b392738ccf3f987d68400dafcf4b0624a56c"


def _workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_aws_oidc_workflow_is_manual_only_and_gated() -> None:
    source = _workflow()

    assert "workflow_dispatch:" in source

    assert not re.search(
        r"(?m)^\s{2}push\s*:",
        source,
    )

    assert not re.search(
        r"(?m)^\s{2}pull_request\s*:",
        source,
    )

    assert not re.search(
        r"(?m)^\s{2}schedule\s*:",
        source,
    )

    branch_gate = 'test "${GITHUB_REF}" = "refs/heads/main"'

    confirmation_gate = 'test "${VALIDATE_CONFIRMATION}" = "VALIDATE_AWS"'

    assert branch_gate in source
    assert confirmation_gate in source

    assert source.index(branch_gate) < source.index("aws-actions/configure-aws-credentials")

    assert source.index(confirmation_gate) < source.index("aws-actions/configure-aws-credentials")


def test_aws_oidc_workflow_has_minimal_oidc_permissions() -> None:
    source = _workflow()

    assert "contents: read" in source

    assert "id-token: write" in source

    assert "packages: write" not in source

    assert "actions: write" not in source

    assert "security-events: write" not in source


def test_configure_aws_credentials_action_is_full_sha_pinned() -> None:
    source = _workflow()

    match = re.search(
        (
            r"uses:\s*"
            r"aws-actions/configure-aws-credentials"
            r"@([0-9a-f]{40})"
        ),
        source,
    )

    assert match is not None

    assert match.group(1) == CONFIGURE_AWS_CREDENTIALS_SHA

    all_action_refs = re.findall(
        r"(?m)^\s*uses:\s*[^@\s]+@([^\s#]+)",
        source,
    )

    assert all_action_refs

    assert all(
        re.fullmatch(
            r"[0-9a-f]{40}",
            ref,
        )
        for ref in all_action_refs
    )


def test_aws_oidc_workflow_uses_non_secret_role_and_region_variables() -> None:
    source = _workflow()

    assert "${{ vars.AWS_GITHUB_OIDC_ROLE_ARN }}" in source

    assert "${{ vars.AWS_AI_REGION }}" in source

    assert "secrets." not in source

    assert "role-to-assume:" in source

    assert "aws-region:" in source

    assert "audience: sts.amazonaws.com" in source

    assert "role-duration-seconds: 900" in source


def test_aws_oidc_workflow_hardens_credential_acquisition() -> None:
    source = _workflow()

    assert "disable-retry: true" in source

    assert "mask-aws-account-id: true" in source

    assert "unset-current-credentials: true" in source

    assert "aws-access-key-id:" not in source

    assert "aws-secret-access-key:" not in source

    assert "aws-session-token:" not in source

    static_environment_names = (
        "AWS_" + "ACCESS_KEY_ID",
        "AWS_" + "SECRET_ACCESS_KEY",
        "AWS_" + "SESSION_TOKEN",
    )

    for name in static_environment_names:
        assert name not in source


def test_aws_oidc_workflow_performs_identity_only_smoke_validation() -> None:
    source = _workflow()

    assert source.count("aws sts get-caller-identity") == 1

    assert "AWS caller identity is not an assumed-role session." in source

    forbidden_service_command = re.compile(
        r"(?mi)^\s*aws\s+"
        r"(?:"
        r"s3|"
        r"s3api|"
        r"sqs|"
        r"sns|"
        r"bedrock|"
        r"bedrock-runtime|"
        r"textract|"
        r"iam|"
        r"cloudformation|"
        r"ecs|"
        r"ecr"
        r")\b"
    )

    assert forbidden_service_command.search(source) is None


def test_aws_oidc_workflow_does_not_use_github_environment_subject() -> None:
    source = _workflow()

    assert not re.search(
        r"(?m)^\s+environment\s*:",
        source,
    )


def test_aws_oidc_workflow_contains_no_trailing_whitespace_or_tabs() -> None:
    source = _workflow()

    for line in source.splitlines():
        assert line.rstrip() == line

        assert "\t" not in line
