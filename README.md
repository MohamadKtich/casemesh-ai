# CaseMesh AI

> **Status:** Active development. Core application, MCP integration, Azure dev deployment, and hardened CI/CD pipelines are operational.

CaseMesh AI is a full-stack, agentic AI case investigation and resolution platform designed for evidence-grounded reasoning, controlled automation, and auditable business actions.

The project combines hybrid retrieval, structured AI orchestration, deterministic tools, human approval, MCP-based integrations, authentication, cloud deployment, and production-oriented delivery practices while following a local-first and zero-cost-first engineering strategy.

## What CaseMesh AI does

A user can create and investigate a case through a workflow that can:

1. ingest and validate evidence,
2. retrieve relevant knowledge using semantic and lexical search,
3. generate evidence-grounded findings,
4. orchestrate specialized investigation steps,
5. use deterministic tools for structured operations,
6. produce a resolution recommendation,
7. protect sensitive actions behind explicit authorization,
8. expose approved business capabilities through MCP,
9. authenticate users through Microsoft Entra ID,
10. record operational state for audit and troubleshooting.

## Engineering principles

- **Local-first:** core development can run locally without permanent cloud infrastructure.
- **Zero-cost-first:** cloud resources are used only when they provide concrete validation or portfolio value.
- **Evidence-grounded AI:** retrieval and citations are preferred over unsupported generation.
- **Deterministic where possible:** calculations and structured transformations belong in code.
- **Controlled agentic behavior:** AI does not receive unrestricted write access.
- **Human and policy controls:** high-impact actions require explicit authorization.
- **Provider abstraction:** AI providers remain replaceable behind application-level interfaces.
- **Defense in depth:** repository, workflow, identity, container, API, and cloud controls are layered.
- **Observable delivery:** CI, deployment verification, health checks, and rollback behavior are explicit.

## Current architecture

```text
Browser
  |
  v
Azure Static Web Apps
React + Vite + TypeScript
  |
  | Microsoft Entra authentication
  v
Azure Container Apps
FastAPI / Python 3.12
  |
  +--> Case management
  +--> Evidence processing
  +--> Hybrid retrieval
  +--> Agentic investigation workflows
  +--> Deterministic tools
  +--> MCP server and client
  +--> Controlled business actions
  |
  v
PostgreSQL + pgvector
```

The API is deployed independently from the frontend. This keeps runtime, release, and rollback concerns separated.

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
- semantic and lexical retrieval
- structured investigation workflows
- deterministic tools
- configurable embedding and generation providers
- MCP server, client, tools, authentication, and transports

### Platform

- Docker
- Docker Compose
- Azure Container Apps
- Azure Static Web Apps
- Azure Bicep
- GitHub Container Registry
- GitHub Actions
- Microsoft Entra ID
- GitHub OIDC federation with Azure

## Hybrid retrieval

CaseMesh combines semantic and lexical retrieval instead of depending on a single search strategy.

```text
User Query
   |
   +--> Semantic Retrieval
   |       |
   |       v
   |    pgvector
   |
   +--> Lexical Retrieval
           |
           v
   PostgreSQL Full-Text Search
           |
           v
        Merge
           |
           v
        Rerank
           |
           v
   Grounded Context
           |
           v
      AI Synthesis
```

The application is designed to preserve source metadata so generated findings can remain traceable to retrieved evidence.

## Agentic workflow design

CaseMesh deliberately avoids turning every operation into an unrestricted autonomous agent.

The architecture separates:

- planning and workflow coordination,
- knowledge retrieval,
- evidence analysis,
- policy and risk reasoning,
- deterministic calculations,
- resolution generation,
- approval and action execution.

Read-only operations can be automated more freely.

Write-side or high-impact operations remain behind explicit application controls.

## MCP integration

CaseMesh includes an MCP integration layer for controlled external actions.

The implementation includes:

- MCP server,
- MCP client,
- authenticated MCP access,
- structured tool definitions,
- HTTP and stdio transport support,
- action authorization,
- integration with investigation workflows.

MCP is used as an integration boundary rather than as a replacement for normal internal application functions.

## Authentication

The deployed application uses Microsoft Entra ID.

The frontend authenticates users through MSAL, while Azure Container Apps authentication protects API access.

Public health endpoints remain available for operational readiness checks.

## CI quality gates

Three independent CI workflows run automatically for changes to `main` and pull requests targeting `main`.

### API CI

Validates:

- dependency integrity,
- Ruff,
- MyPy,
- pytest.

### Web CI

Validates:

- reproducible dependency installation with `npm ci`,
- Oxlint,
- production frontend build.

### Platform CI

Validates:

- Docker Compose configuration,
- API container build,
- non-root container runtime user,
- expected container working directory,
- Azure CLI availability,
- Azure Bicep compilation.

## Deployment model

Deployments to the Azure dev environment are intentionally manual.

This prevents every source change from creating unnecessary cloud revisions or consuming cloud resources.

### API deployment

The API deployment workflow:

1. requires the `main` branch,
2. requires explicit `DEPLOY` confirmation,
3. builds the API container,
4. publishes an immutable image to GHCR using the Git commit SHA,
5. authenticates to Azure through GitHub OIDC,
6. updates the Azure Container App,
7. waits for the exact new revision,
8. verifies `/health/ready`,
9. verifies the exact image and revision,
10. rolls back to the previous image if deployment verification fails.

Container images use immutable references in the form:

```text
ghcr.io/mohamadktich/casemesh-api:<git-sha>
```

### Frontend deployment

The frontend deployment workflow:

1. requires the `main` branch,
2. requires explicit `DEPLOY` confirmation,
3. validates required deployment configuration,
4. installs dependencies with `npm ci`,
5. runs linting,
6. creates the production Vite build,
7. verifies the configured production API endpoint is embedded,
8. deploys the prebuilt application to Azure Static Web Apps,
9. verifies the production website responds successfully.

## CI/CD security

The GitHub Actions configuration is hardened with:

- minimum required workflow permissions,
- GitHub Actions pinned to immutable commit SHAs,
- `persist-credentials: false` on repository checkout,
- Azure authentication through OIDC instead of a stored Azure client secret,
- restricted `packages: write` permission only where GHCR publishing is required,
- `id-token: write` only for the Azure deployment workflow,
- repository variables for non-secret deployment configuration,
- GitHub Secrets for sensitive deployment tokens,
- manual deployment confirmation,
- immutable API image tags,
- post-deployment verification and API rollback.

## Secret handling

Secrets are not committed to Git.

Local environment files such as `.env` and `.env.local` are ignored.

Azure infrastructure secret inputs are declared as secure Bicep parameters.

The repository contains only safe example configuration files.

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

The Azure environment exists for development validation and portfolio demonstration. It is not presented as a production SLA environment.

## Zero-cost-first cloud strategy

CaseMesh avoids requiring permanently paid infrastructure for normal development.

The project favors:

- local development,
- open-source components,
- free service tiers where appropriate,
- scale-to-zero cloud compute,
- small dev resource limits,
- targeted cloud validation,
- manual deployments instead of deployment on every commit.

The architecture can be expanded later without making paid infrastructure a prerequisite for contributing to or evaluating the project.

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
|
+-- scripts/                     # Validation and utility scripts
|
+-- .github/
|   +-- workflows/
|       +-- api-ci.yml
|       +-- api-deploy-dev.yml
|       +-- platform-ci.yml
|       +-- web-ci.yml
|       +-- web-deploy-dev.yml
|
+-- ARCHITECTURE.md
+-- CONTRIBUTING.md
+-- ROADMAP.md
+-- SECURITY.md
+-- README.md
```

## Active GitHub Actions workflows

```text
CaseMesh API CI
CaseMesh Web CI
CaseMesh Platform CI
CaseMesh API Deploy Dev
CaseMesh Web Deploy Dev
```

Diagnostic deployment workflows used during initial OIDC and GHCR validation were intentionally removed after the permanent deployment workflows were verified.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Security Policy](SECURITY.md)
- [Contribution Guide](CONTRIBUTING.md)
- [Roadmap](ROADMAP.md)
- [GitHub Setup](docs/GITHUB_SETUP.md)
- [Development Setup](docs/DEVELOPMENT_SETUP.md)
- [Project Checklist](docs/PROJECT_CHECKLIST.md)

## Project positioning

CaseMesh AI is an engineering portfolio project focused on demonstrating practical experience across:

- AI engineering,
- RAG systems,
- agentic workflows,
- MCP,
- backend engineering,
- frontend integration,
- authentication,
- cloud architecture,
- Infrastructure as Code,
- containerization,
- CI/CD,
- deployment safety,
- security-oriented engineering.

The goal is not to maximize the number of technologies used. The goal is to show how AI capabilities can be integrated into a controlled, testable, deployable software system.

## License

MIT License. See [LICENSE](LICENSE).
