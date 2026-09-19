# AWS Intelligence v1.1

## Scope

AWS Intelligence v1.1 adds a bounded cross-cloud intelligence layer to CaseMesh without changing the core application authority model.

Azure remains the current application hosting environment. AWS is used as a specialized intelligence extension for document processing, asynchronous completion, second-review reasoning, guardrails, alerts, and cross-cloud validation.

The design remains local-first and zero-cost-first. Cloud capabilities are opt-in and disabled by default.

## Architectural role

```text
CaseMesh investigation workflow
        |
        +--> local / primary application path
        |
        +--> optional AWS intelligence gateway
                  |
                  +--> S3 temporary staging
                  +--> Textract document intelligence
                  +--> SQS async completion
                  +--> Bedrock second review
                  +--> Bedrock Guardrails
                  +--> SNS escalation alerts
```

AWS intelligence can review, enrich, or escalate an investigation. It does not receive authority to execute privileged business actions.

`PolicyGuard` and the application action controls remain authoritative for write-side and sensitive operations.

## Identity model

GitHub Actions authenticates to AWS through GitHub OIDC and short-lived STS credentials.

No static AWS access key or secret key is required for the validation workflows.

Validated identity path:

```text
GitHub Actions
    |
    | OIDC token
    v
AWS IAM OIDC provider
    |
    v
CaseMeshGitHubOIDC IAM role
    |
    | AssumeRoleWithWebIdentity
    v
Short-lived AWS session
```

The trust relationship is restricted to the CaseMesh repository and `main` branch for manual validation workflows.

## Bedrock validation

The project completed two levels of real Bedrock validation.

### 1. Bounded provider-level inference

A manual GitHub Actions workflow validated a single bounded Bedrock inference call through GitHub OIDC.

Validated properties:

- GitHub OIDC authentication succeeded,
- the IAM role was assumed successfully,
- the Bedrock runtime request succeeded,
- the request used a strict output-token bound,
- the model response body was not printed to workflow logs,
- no application action was executed.

The provider-level validation used the EU Amazon Nova Micro inference profile.

### 2. Real CaseMesh application path

A second manual workflow validated the real CaseMesh second-review path rather than calling Bedrock directly from the AWS CLI.

The validation exercised:

```text
GitHub OIDC
    |
    v
AWS IAM role
    |
    v
CaseMesh AWS Bedrock provider
    |
    v
InvestigationWorkflow._second_review()
    |
    v
Structured second-review result
```

The successful application-path validation used the EU Anthropic Claude Haiku 4.5 inference profile because the CaseMesh second-review adapter requires structured output support.

Validated properties included:

- real `aws-bedrock` provider construction,
- real Bedrock invocation through CaseMesh,
- structured review completion,
- bounded second-review budget,
- safe routing to either continuation or human review,
- no privileged action execution,
- no raw model response logging.

## Safety model

AWS Intelligence v1.1 is intentionally advisory and fail-safe.

The test suite verifies that:

- provider failures fail closed,
- Bedrock or guardrail failures do not break the investigation workflow,
- disagreement or uncertainty can force human review,
- second-review attempts are budget-limited,
- high-risk actions require approval,
- financial actions remain protected by policy controls,
- second review cannot downgrade an authoritative policy block,
- cross-cloud alert failures remain isolated,
- raw infrastructure error details are not exposed through safe API summaries.

A dedicated offline safety workflow runs these regression tests without AWS credentials and without real AWS calls.

## Service coverage

AWS Intelligence v1.1 contains application adapters and tests for:

- AWS client and gateway construction,
- temporary S3 staging and lifecycle behavior,
- Textract document intelligence,
- SQS asynchronous processing and completion,
- Bedrock second review,
- Bedrock Guardrails,
- risk-trigger routing,
- SNS alert delivery,
- idempotency and replay behavior,
- request timeouts,
- budget boundaries,
- cross-cloud failure isolation,
- federated identity refresh,
- safe API/UI summaries.

Not every adapter is exercised against a live AWS resource during normal development. Mock and contract-first testing is the default, with real cloud calls reserved for targeted validation that adds concrete engineering evidence.

## Regions and models

The validated Bedrock path uses an EU region because it provides a working, cost-controlled model path for the current account and validation requirements.

Example configuration:

```text
AWS_AI_REGION=eu-north-1
AWS_CLIENT_MODE=sdk
AWS_IDENTITY_MODE=default_chain
AWS_BEDROCK_REVIEW_ENABLED=true
AWS_MAX_REVIEWS_PER_INVESTIGATION=1
```

Model IDs are configuration, not application authority. Production or future environments should select supported inference profiles and re-validate least-privilege IAM resources before use.

## IAM principles

The GitHub OIDC role is intentionally narrower than an administrator or broad Bedrock role.

The validation policy grants only the actions and resources needed for the bounded Bedrock checks, while catalog listing remains read-only.

Do not attach `AdministratorAccess` or broad account-wide permissions merely to resolve a model-access error.

## Validation workflows

Manual validation workflows retained in the repository provide reproducible evidence for the AWS integration:

```text
CaseMesh AWS OIDC Validate
CaseMesh AWS Bedrock Catalog Validate
CaseMesh AWS Bedrock Inference Validate
CaseMesh AWS Application Path Validate
CaseMesh AWS Safety Validate
CaseMesh Final Full Regression
```

These workflows are intentionally manual. They are not a requirement for every source change and should not create repeated model calls during routine CI.

## Final validation status

AWS Intelligence v1.1 completed the following validation sequence:

```text
OIDC identity validation                 PASS
Bedrock catalog validation               PASS
Bounded real Bedrock inference           PASS
Real CaseMesh second-review path         PASS
Offline fail-safe regression             PASS
Final API/Web/Platform regression         PASS
```

The final regression gate validates API linting, typing and tests; frontend lint and build; Docker Compose; API container runtime properties; Azure Bicep compilation; and clean tracked working trees.

## Cost controls

The integration follows the project-wide zero-cost-first strategy:

- real model calls are manually triggered,
- validation calls are bounded,
- second-review attempts are capped,
- normal CI does not invoke Bedrock,
- mock and contract tests cover failure behavior,
- no permanently running AWS infrastructure is required for core development.

## Security boundary

AWS Intelligence v1.1 does not change the central CaseMesh rule:

> AI output is evidence and advice, not authorization.

Sensitive actions remain subject to deterministic policy, approval, and action-execution controls outside the model.