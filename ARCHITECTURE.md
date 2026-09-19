# CaseMesh AI Architecture

## 1. Architecture goal

CaseMesh AI is a full-stack, production-oriented AI engineering project for evidence-grounded case investigation, controlled agentic workflows, and auditable business actions.

The architecture is designed around the following principles:

- evidence grounding over unsupported generation,
- deterministic code where deterministic logic is sufficient,
- controlled agentic behavior instead of unrestricted autonomy,
- explicit authorization boundaries for sensitive actions,
- provider abstraction instead of vendor lock-in,
- local-first development,
- zero-cost-first cloud usage,
- independently deployable frontend and API layers,
- reproducible CI and intentionally manual cloud deployment,
- defense in depth across repository, workflow, identity, container, API, and cloud layers.

## 2. System overview

```text
User Browser
    |
    v
Azure Static Web Apps
React + Vite + TypeScript
    |
    | Microsoft Entra ID authentication
    v
Azure Container Apps
FastAPI / Python 3.12
    |
    +--> Authentication-aware API routes
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

The frontend and backend are deployed independently. This allows the web application and API to evolve, validate, and roll back without forcing a single deployment unit.

## 3. Application layers

### 3.1 Web layer

**React 19 + Vite + TypeScript**

Responsibilities include:

- authenticated user entry point,
- case and investigation interfaces,
- interaction with the CaseMesh API,
- Microsoft Entra sign-in through MSAL,
- production configuration through Vite environment variables.

The frontend does not contain the system's AI orchestration logic or business action authorization.

### 3.2 API layer

**FastAPI + Python 3.12**

Responsibilities include:

- HTTP API contracts,
- request validation,
- authentication-aware access,
- case operations,
- evidence processing,
- retrieval requests,
- investigation workflows,
- controlled tool execution,
- MCP integration,
- health and readiness endpoints.

The API is the primary application boundary between the user-facing web layer and the domain, retrieval, workflow, and integration components.

### 3.3 Domain and service layer

Core concepts include:

- users,
- cases,
- evidence,
- investigation state,
- retrieved knowledge,
- generated findings,
- actions,
- audit-relevant execution state.

The LLM is not treated as the source of truth. Application state and deterministic validation remain outside the model.

## 4. Data architecture

### PostgreSQL

PostgreSQL is used as the primary relational persistence layer.

### pgvector

pgvector enables semantic vector retrieval inside PostgreSQL.

### PostgreSQL Full-Text Search

PostgreSQL Full-Text Search provides lexical retrieval for terms, identifiers, and keyword-sensitive queries.

### Local and development data

Local-first development avoids requiring permanently running cloud data services.

Private or sensitive datasets are intentionally excluded from the repository.

## 5. Hybrid retrieval

CaseMesh uses both semantic and lexical retrieval.

```text
Query
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
  Reciprocal Rank Fusion (RRF)
          |
          v
    Ranked Evidence
          |
          v
   Grounded Context
          |
          v
      AI Synthesis
```

The retrieval design is intended to preserve source metadata so generated findings can remain traceable to evidence.

The model does not replace retrieval. Retrieval supplies grounded context to the model.

## 6. Agentic workflow model

CaseMesh uses structured agentic workflows rather than treating every operation as an autonomous agent.

The architecture separates concerns such as:

- workflow planning,
- knowledge retrieval,
- evidence analysis,
- policy and risk reasoning,
- deterministic calculations,
- resolution generation,
- controlled action execution.

This design reduces unnecessary model calls and keeps critical behavior observable and testable.

## 7. Deterministic tools

Operations that can be implemented reliably in code stay in code.

Examples include:

- structured retrieval,
- calculations,
- validation,
- state transitions,
- authorization checks,
- controlled data transformations.

LLMs are used where language understanding, synthesis, or reasoning over unstructured context is useful.

## 8. Action safety model

Read-oriented operations can be less restrictive than write-side actions.

Sensitive operations are protected through explicit application controls.

The current design includes:

- action execution switches,
- execution modes,
- live-action allowlists,
- authenticated MCP access,
- deterministic validation before controlled actions.

The architecture is designed so model output alone does not grant permission to perform a sensitive business action.

## 9. MCP integration

MCP is used as a standardized integration boundary for approved business capabilities.

The implementation includes:

- MCP server,
- MCP client,
- MCP authentication,
- structured tool definitions,
- stdio support,
- remote transport support,
- integration with investigation workflows.

MCP is not used as a replacement for normal internal Python functions. It is reserved for capabilities that benefit from a structured tool or integration boundary.

## 10. AI provider abstraction

Embedding and generation behavior is configured through application-level provider settings.

This keeps the system from depending directly on one model vendor throughout the codebase.

The provider abstraction supports the project's goals of:

- local-first development,
- replaceable AI providers,
- cloud validation when useful,
- cost-aware experimentation.

Provider-specific credentials are not committed to source control.

## 11. Authentication architecture

The deployed application uses Microsoft Entra ID.

```text
Browser
  |
  | MSAL sign-in
  v
Microsoft Entra ID
  |
  v
Frontend
  |
  | authenticated API request
  v
Azure Container Apps authentication
  |
  v
FastAPI
```

The frontend uses MSAL configuration supplied at build time.

Azure Container Apps authentication protects API access.

Operational health endpoints remain available for readiness verification.

## 12. Container architecture

The API is packaged as a Docker container.

Security-relevant container properties include:

- Python 3.12 slim base image,
- non-root runtime user,
- fixed application working directory,
- container health check,
- production execution through Uvicorn.

Platform CI verifies the expected runtime user and working directory.

## 13. Azure infrastructure

The Azure dev environment currently uses:

- Azure Container Apps for the API,
- Azure Static Web Apps for the frontend,
- Microsoft Entra ID for authentication,
- Azure Bicep for Infrastructure as Code.

The Azure Container App is configured with a small dev footprint and scale-to-zero behavior.

The Static Web App uses the Free tier for the current dev/portfolio environment.

## 14. Infrastructure as Code

Azure infrastructure is defined using Bicep.

Key infrastructure properties include:

- explicit container image input,
- secure Bicep parameters for secrets,
- Container Apps environment provisioning,
- Container App configuration,
- Static Web App provisioning,
- authentication configuration,
- CORS configuration.

The container image is intentionally supplied by the deployment caller rather than pinned as a stale default in infrastructure code.

This keeps runtime image ownership with the deployment workflow.

## 15. CI architecture

CaseMesh separates quality checks into three workflows.

### API CI

Runs automatically on pushes to `main` and pull requests targeting `main`.

Validates:

- dependency integrity,
- Ruff,
- MyPy,
- pytest.

### Web CI

Runs automatically on pushes to `main` and pull requests targeting `main`.

Validates:

- reproducible installation with `npm ci`,
- Oxlint,
- production frontend build.

### Platform CI

Runs automatically on pushes to `main` and pull requests targeting `main`.

Validates:

- Docker Compose configuration,
- API container build,
- non-root runtime user,
- expected working directory,
- Azure CLI availability,
- Bicep compilation.

## 16. CI/CD supply-chain controls

The GitHub Actions configuration is hardened with:

- minimum required workflow permissions,
- external Actions pinned to full immutable commit SHAs,
- `persist-credentials: false` for repository checkout,
- separate CI and deployment workflows,
- manual deployment confirmation,
- restricted package publishing permissions,
- OIDC-based Azure authentication.

CI workflows do not receive deployment permissions.

The API deployment workflow receives only the additional permissions required for GHCR publishing and Azure OIDC.

## 17. API deployment architecture

API deployment is manual.

```text
Manual GitHub Actions dispatch
        |
        | require main + DEPLOY confirmation
        v
Build API image
        |
        v
Push immutable image to GHCR
        |
        | tag = Git commit SHA
        v
GitHub OIDC -> Azure
        |
        v
Update Azure Container App
        |
        v
Wait for exact new revision
        |
        v
Verify /health/ready
        |
        v
Verify exact image + revision
        |
        +--> success
        |
        +--> failure -> rollback to previous image
```

Images are published using immutable references:

```text
ghcr.io/mohamadktich/casemesh-api:<git-sha>
```

The workflow verifies that the exact expected image became the exact ready revision.

If deployment verification fails after the update, the workflow attempts to restore the previous image and verifies the rollback revision.

## 18. Frontend deployment architecture

Frontend deployment is also manual.

```text
Manual GitHub Actions dispatch
        |
        | require main + DEPLOY confirmation
        v
Validate deployment configuration
        |
        v
npm ci
        |
        v
Oxlint
        |
        v
Production Vite build
        |
        v
Verify compiled API endpoint
        |
        v
Deploy prebuilt output
        |
        v
Azure Static Web Apps
        |
        v
HTTP production verification
```

The frontend deployment does not rely on Azure to perform an uncontrolled application build.

The workflow builds the application first, validates it, and deploys the prepared output.

## 19. Identity between GitHub and Azure

Azure deployment authentication uses GitHub OIDC federation.

This avoids storing an Azure client secret in the GitHub repository.

The deployment identity is scoped to the Azure dev resource group and is used by the API deployment workflow.

Repository variables store non-secret Azure identifiers.

Sensitive deployment tokens remain GitHub Secrets.

## 20. Runtime verification

Deployment success is not defined only as "the command completed."

The API deployment verifies:

- a new revision was created,
- the new revision is the ready revision,
- the revision uses the expected immutable image,
- `/health/ready` returns successfully,
- the database readiness state is connected.

The frontend deployment verifies:

- the production build exists,
- the expected API URL is compiled into the frontend,
- the deployed site responds over HTTPS,
- the returned page contains the expected React root element.

## 21. Security principles

CaseMesh applies layered security controls:

- no secrets committed to Git,
- ignored local environment files,
- safe example environment files,
- secure Bicep secret parameters,
- non-root API container,
- HTTPS-only production API configuration,
- Microsoft Entra authentication,
- least-privilege GitHub Actions permissions,
- SHA-pinned Actions,
- disabled checkout credential persistence,
- OIDC instead of a stored Azure client secret,
- controlled MCP authentication,
- explicit action-execution controls,
- deployment verification and rollback.

## 22. Zero-cost-first strategy

The architecture deliberately avoids making paid cloud infrastructure a requirement for normal development.

The project favors:

- local execution,
- open-source components,
- free tiers where appropriate,
- scale-to-zero compute,
- small dev resource limits,
- targeted cloud validation,
- manual deployment instead of deploy-on-every-commit.

Cloud usage exists to prove real integration and deployment behavior, not to create a permanent cost dependency.

## 23. Current dev deployment

Frontend:

```text
https://zealous-pebble-08744c900.5.azurestaticapps.net
```

API:

```text
https://casemesh-api-dev.lemonwater-0bb11448.uaenorth.azurecontainerapps.io
```

Readiness endpoint:

```text
https://casemesh-api-dev.lemonwater-0bb11448.uaenorth.azurecontainerapps.io/health/ready
```

This environment is intended for development validation and portfolio demonstration. It is not represented as a production SLA environment.

## 24. Architectural direction

Future work can extend the system with additional provider integrations, evaluation, observability, FinOps, and portfolio release assets without changing the core architectural boundaries.

The most important constraint remains unchanged:

**AI capabilities must remain controlled, testable, evidence-grounded, and deployable as normal software rather than treated as an opaque autonomous subsystem.**
