# CaseMesh AI

> **Status:** Core platform operational. Azure dev deployment, hardened CI/CD, MCP integration, and AWS Intelligence v1.1 validation are complete.

CaseMesh AI is a full-stack, agentic AI case investigation and resolution platform designed for evidence-grounded reasoning, controlled automation, human approval, and auditable business actions.

The project combines hybrid retrieval, structured investigation workflows, deterministic tools, MCP integrations, Microsoft Entra authentication, Azure deployment, and a bounded AWS intelligence layer while following a local-first and zero-cost-first engineering strategy.

## What CaseMesh AI does

A CaseMesh investigation can:

1. ingest and validate evidence,
2. retrieve relevant knowledge through semantic and lexical search,
3. generate evidence-grounded findings with citations,
4. orchestrate structured investigation steps,
5. use deterministic tools where code is more reliable than generation,
6. request an independent second review,
7. identify risk and uncertainty,
8. route sensitive cases to human review,
9. protect write-side actions behind deterministic policy and approval,
10. expose approved capabilities through MCP,
11. record operational state for audit and troubleshooting.

## Engineering principles

- **Evidence-grounded AI:** retrieved evidence and citations are preferred over unsupported generation.
- **Controlled agentic behavior:** models do not receive unrestricted write access.
- **Deterministic where possible:** calculations, validation, authorization, and state transitions stay in code.
- **Policy authority outside the model:** AI review cannot override `PolicyGuard` or approval requirements.
- **Provider abstraction:** model and cloud integrations remain replaceable behind application interfaces.
- **Local-first:** normal development does not require permanent cloud infrastructure.
- **Zero-cost-first:** real cloud calls are targeted, bounded, and manually triggered when they add engineering evidence.
- **Defense in depth:** repository, CI/CD, identity, container, API, MCP, and cloud controls are layered.
- **Observable delivery:** CI, deployment verification, readiness checks, rollback behavior, and validation workflows are explicit.

## Architecture

```text
User Browser
    |
    v
Azure Static Web Apps
React + Vite + TypeScript
    |
    | Microsoft Entra ID
    v
Azure Container Apps
FastAPI / Python 3.12
    |
    +--> Case management
    +--> Evidence processing
    +--> Hybrid retrieval
    +--> Agentic investigation workflow
    +--> Deterministic tools
    +--> MCP integration
    +--> PolicyGuard + approval controls
    |
    +--> Optional AWS Intelligence v1.1
    |       +--> S3 temporary staging
    |       +--> Textract document intelligence
    |       +--> SQS async completion
    |       +--> Bedrock second review
    |       +--> Bedrock Guardrails
    |       +--> SNS escalation alerts
    |
    v
PostgreSQL + pgvector
```

Azure is the current hosting environment. AWS is an opt-in specialized intelligence extension, not a replacement for the core application authority model.

## Technology stack

### Frontend

- React 19
- TypeScript
- Vite
- Microsoft Authentication Library (MSAL)
- Oxlint

### Backend

- Python 3.12
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- pgvector
- pytest
- Ruff
- MyPy

### AI and orchestration

- retrieval-augmented generation
- semantic + lexical retrieval
- structured investigation workflows
- deterministic tools
- configurable AI providers
- bounded second-review reasoning
- MCP server/client/tools/authentication/transports

### Cloud and delivery

- Azure Container Apps
- Azure Static Web Apps
- Azure Bicep
- Microsoft Entra ID
- AWS IAM + GitHub OIDC
- Amazon Bedrock
- AWS integration adapters for S3, Textract, SQS, Guardrails, and SNS
- Docker / Docker Compose
- GitHub Container Registry
- GitHub Actions

## Hybrid retrieval

```text
User Query
   |
   +--> Semantic Retrieval --> pgvector
   |
   +--> Lexical Retrieval  --> PostgreSQL FTS
   |
   v
Merge + Rerank
   |
   v
Grounded Context
   |
   v
AI Synthesis + Citations
```

CaseMesh preserves source metadata so findings can remain traceable to retrieved evidence.

## Agentic workflow and safety model

CaseMesh deliberately avoids unrestricted autonomous execution.

The workflow separates:

- planning and coordination,
- retrieval,
- evidence analysis,
- AI-assisted reasoning,
- policy and risk evaluation,
- deterministic calculations,
- human review,
- controlled action execution.

Sensitive actions remain behind explicit application controls. A model response alone never grants permission to execute a financial, privileged, or high-risk action.

## AWS Intelligence v1.1

AWS Intelligence v1.1 adds a bounded cross-cloud review and document-intelligence layer.

The implemented architecture includes:

- AWS client/gateway abstraction,
- temporary S3 staging and lifecycle handling,
- Textract document intelligence,
- SQS asynchronous completion,
- Bedrock second review,
- Bedrock Guardrails integration,
- risk-trigger routing,
- SNS escalation alerts,
- idempotency and replay controls,
- request timeouts and review budgets,
- cross-cloud failure isolation,
- federated identity support,
- safe API summaries that avoid raw infrastructure leakage.

### Real cloud validation completed

The project has verified:

- GitHub OIDC to AWS IAM using short-lived credentials,
- Bedrock catalog access,
- one bounded real Bedrock inference,
- the real CaseMesh second-review application path through Bedrock,
- offline fail-safe behavior for provider, guardrail, alert, risk, and policy failures,
- final API/Web/Platform regression after the AWS integration.

Normal CI does **not** call Bedrock. Real model calls remain manual and bounded.

See [AWS Intelligence v1.1](docs/AWS_INTELLIGENCE_V1_1.md) for the validation record and security boundaries.

## MCP integration

CaseMesh includes an MCP integration layer with:

- MCP server,
- MCP client,
- authenticated MCP access,
- structured tool definitions,
- HTTP and stdio transport support,
- application-level authorization,
- investigation-workflow integration.

MCP is treated as an integration boundary, not a bypass around normal application policy.

## Authentication and cloud identity

### Application users

The deployed application uses Microsoft Entra ID. The frontend signs users in through MSAL, while Azure Container Apps authentication protects API access.

### GitHub to Azure

Azure deployment uses GitHub OIDC federation rather than a stored Azure client secret.

### GitHub to AWS

Manual AWS validation workflows use GitHub OIDC with `AssumeRoleWithWebIdentity` and short-lived STS sessions. Static AWS access keys are not required.

## CI quality gates

Three independent CI workflows run automatically for changes to `main` and pull requests targeting `main`.

### API CI

- dependency integrity
- Ruff
- MyPy
- pytest

### Web CI

- `npm ci`
- Oxlint
- production build

### Platform CI

- Docker Compose validation
- API container build
- non-root runtime user verification
- expected container working directory
- Azure Bicep compilation

A separate manual **CaseMesh Final Full Regression** workflow re-runs the complete API, Web, and Platform quality gates before a portfolio/release checkpoint.

## Deployment model

Cloud deployment is intentionally manual.

### API deployment

The API workflow:

1. requires `main`,
2. requires explicit `DEPLOY` confirmation,
3. builds the API image,
4. publishes an immutable GHCR image tagged with the Git commit SHA,
5. authenticates to Azure through GitHub OIDC,
6. updates Azure Container Apps,
7. waits for the exact new revision,
8. verifies `/health/ready`,
9. verifies the exact image/revision,
10. rolls back to the previous image if verification fails.

### Frontend deployment

The frontend workflow:

1. requires `main`,
2. requires explicit `DEPLOY` confirmation,
3. installs dependencies reproducibly,
4. runs linting,
5. builds the production Vite app,
6. verifies the compiled production API endpoint,
7. deploys the prebuilt output to Azure Static Web Apps,
8. verifies the production site over HTTPS.

## CI/CD security

GitHub Actions are hardened with:

- minimum workflow permissions,
- external Actions pinned to immutable commit SHAs,
- `persist-credentials: false`,
- OIDC instead of stored Azure/AWS long-lived cloud credentials,
- `id-token: write` only where federation is required,
- restricted package publishing permissions,
- manual deployment and real-cloud validation confirmation,
- immutable API image tags,
- post-deployment verification and rollback.

## Azure dev environment

Current dev deployment:

```text
Frontend
https://zealous-pebble-08744c900.5.azurestaticapps.net

API
https://casemesh-api-dev.lemonwater-0bb11448.uaenorth.azurecontainerapps.io

API readiness
https://casemesh-api-dev.lemonwater-0bb11448.uaenorth.azurecontainerapps.io/health/ready
```

This environment is for development validation and portfolio demonstration, not a production SLA environment.

## Zero-cost-first strategy

CaseMesh avoids making permanently paid infrastructure a prerequisite for development.

The project favors:

- local execution,
- open-source components,
- free tiers where appropriate,
- scale-to-zero compute,
- small dev resource limits,
- manual cloud validation,
- bounded model calls,
- mock/contract testing for failure paths,
- manual deployment instead of deploy-on-every-commit.

## Repository structure

```text
casemesh-ai/
|
+-- apps/
|   +-- api/                     # FastAPI backend
|   +-- web/                     # React + Vite frontend
|
+-- infrastructure/
|   +-- azure/                   # Azure Bicep infrastructure
|
+-- data/                        # Local/synthetic/evaluation data
|
+-- docs/
|   +-- architecture/            # Architecture records
|   +-- images/                  # Architecture diagrams
|   +-- AWS_INTELLIGENCE_V1_1.md
|
+-- scripts/                     # Validation and utility scripts
|
+-- .github/workflows/           # CI, deployment, and manual validation workflows
|
+-- ARCHITECTURE.md
+-- CONTRIBUTING.md
+-- ROADMAP.md
+-- SECURITY.md
+-- README.md
```

## Active GitHub Actions workflows

Core delivery:

```text
CaseMesh API CI
CaseMesh Web CI
CaseMesh Platform CI
CaseMesh API Deploy Dev
CaseMesh Web Deploy Dev
```

Manual AWS and release validation:

```text
CaseMesh AWS OIDC Validate
CaseMesh AWS Bedrock Catalog Validate
CaseMesh AWS Bedrock Inference Validate
CaseMesh AWS Application Path Validate
CaseMesh AWS Safety Validate
CaseMesh Final Full Regression
```

## Documentation

- [Architecture](ARCHITECTURE.md)
- [AWS Intelligence v1.1](docs/AWS_INTELLIGENCE_V1_1.md)
- [Security Policy](SECURITY.md)
- [Contribution Guide](CONTRIBUTING.md)
- [Roadmap](ROADMAP.md)
- [GitHub Setup](docs/GITHUB_SETUP.md)
- [Development Setup](docs/DEVELOPMENT_SETUP.md)
- [Project Checklist](docs/PROJECT_CHECKLIST.md)

## Project positioning

CaseMesh AI is an engineering portfolio project demonstrating practical experience across:

- AI engineering,
- RAG systems,
- agentic workflows,
- MCP,
- backend and frontend engineering,
- authentication and cloud identity,
- multi-cloud integration,
- Infrastructure as Code,
- containerization,
- CI/CD,
- deployment safety,
- security-oriented engineering,
- cost-aware architecture.

The goal is not to maximize the number of technologies. The goal is to show that AI capabilities can be integrated into a controlled, testable, deployable software system with explicit safety boundaries.

## License

MIT License. See [LICENSE](LICENSE).
