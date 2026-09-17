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
    +--> PolicyGuard + controlled business actions
    |
    +--> Optional AWS Intelligence v1.1
    |       |
    |       +--> S3 temporary staging
    |       +--> Textract document intelligence
    |       +--> SQS asynchronous completion
    |       +--> Bedrock second review
    |       +--> Bedrock Guardrails
    |       +--> SNS escalation alerts
    |
    v
PostgreSQL + pgvector
```

Azure remains the current application hosting environment. AWS is a specialized intelligence extension and does not replace the core application authority model.

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
  +--> Semantic Retrieval --> pgvector
  |
  +--> Lexical Retrieval --> PostgreSQL Full-Text Search
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

The retrieval design preserves source metadata so generated findings can remain traceable to evidence.

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
- human review,
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
- deterministic validation before controlled actions,
- human approval for high-impact operations,
- PolicyGuard authority that cannot be downgraded by model output.

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

The provider abstraction supports:

- local-first development,
- replaceable model providers,
- cloud validation when useful,
- cost-aware experimentation,
- optional cross-cloud second review.

Provider-specific credentials are not committed to source control.

## 11. AWS Intelligence v1.1

AWS Intelligence v1.1 is an opt-in cross-cloud intelligence layer that enriches or reviews CaseMesh investigations without taking ownership of business authorization.

### 11.1 Gateway and client boundary

The AWS integration is separated behind application-level gateway/client construction rather than spreading direct boto3 calls through workflow code.

Capabilities include:

- client factory behavior,
- region-aware construction,
- request-timeout controls,
- mock/offline mode,
- SDK mode for targeted real validation.

### 11.2 Temporary S3 staging

Temporary evidence staging supports bounded document workflows with lifecycle-oriented cleanup behavior.

Staging is treated as an integration boundary, not as the authoritative CaseMesh evidence store.

### 11.3 Textract document intelligence

Textract adapters support document extraction, pagination, async completion, and failure normalization.

Document-intelligence failures are isolated from the rest of the investigation workflow and remain subject to application-level handling.

### 11.4 SQS asynchronous completion

SQS supports asynchronous processing and completion flows.

The implementation includes idempotency, replay protection, message-claim behavior, and provider-failure handling so failed work is not acknowledged incorrectly.

### 11.5 Bedrock second review

Bedrock can provide an independent structured review of CaseMesh findings.

```text
Investigation findings
        |
        v
Second-review gate
        |
        v
AWS Bedrock provider
        |
        v
Structured review result
        |
        +--> continue
        |
        +--> human_review
```

The review is advisory. It cannot authorize a blocked action or weaken a PolicyGuard decision.

The second-review budget is explicitly bounded to avoid uncontrolled repeat calls.

### 11.6 Bedrock Guardrails

Guardrail evaluation can fail closed and can force review/escalation behavior.

A guardrail failure is treated as a provider-boundary failure rather than silently ignored.

### 11.7 Risk triggers and SNS alerts

Risk-trigger logic can emit escalation events. SNS alert delivery is isolated so alert transport failure does not mutate approval state or recursively create new cross-cloud failures.

### 11.8 Failure isolation

The integration explicitly handles:

- provider failure,
- timeout,
- review-budget exhaustion,
- replay/idempotency behavior,
- guardrail block/failure,
- cross-cloud failure signaling,
- alert transport failure,
- malformed metadata,
- safe API summaries,
- federated identity refresh.

Cross-cloud intelligence should fail closed and route to human review where necessary rather than breaking the investigation workflow.

## 12. AWS identity architecture

### GitHub Actions to AWS

Manual validation uses GitHub OIDC and AWS STS.

```text
GitHub Actions
    |
    | OIDC
    v
AWS IAM OIDC provider
    |
    v
CaseMeshGitHubOIDC role
    |
    | AssumeRoleWithWebIdentity
    v
Short-lived AWS credentials
```

Static AWS access keys are not required for the validation workflows.

The trust relationship is restricted to the CaseMesh repository and expected branch context.

### Runtime/federated identity support

The codebase also contains federated credential support for short-lived runtime identity paths, including refresh behavior. Long-lived credential persistence is intentionally avoided.

## 13. Authentication architecture

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

## 14. Container architecture

The API is packaged as a Docker container.

Security-relevant container properties include:

- Python 3.12 slim base image,
- non-root runtime user,
- fixed application working directory,
- container health check,
- production execution through Uvicorn.

Platform CI verifies the expected runtime user and working directory.

## 15. Azure infrastructure

The Azure dev environment currently uses:

- Azure Container Apps for the API,
- Azure Static Web Apps for the frontend,
- Microsoft Entra ID for authentication,
- Azure Bicep for Infrastructure as Code.

The Azure Container App is configured with a small dev footprint and scale-to-zero behavior.

The Static Web App uses the Free tier for the current dev/portfolio environment.

## 16. Infrastructure as Code

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

## 17. CI architecture

CaseMesh separates quality checks into three automatic workflows.

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

## 18. Manual validation architecture

Real cloud checks are deliberately manual rather than part of normal CI.

AWS validation workflows include:

- GitHub OIDC identity validation,
- Bedrock catalog validation,
- bounded provider-level Bedrock inference,
- real CaseMesh second-review application-path validation,
- offline AWS safety/failure validation.

A final full-regression workflow re-runs the complete API, Web, and Platform gates without AWS credentials or real AWS calls.

This keeps the repository reproducible while preventing every source change from consuming cloud resources or model tokens.

## 19. CI/CD supply-chain controls

GitHub Actions use:

- minimum required workflow permissions,
- external Actions pinned to full immutable commit SHAs,
- `persist-credentials: false` for repository checkout,
- separate CI and deployment workflows,
- manual deployment confirmation,
- restricted package publishing permissions,
- OIDC-based Azure authentication,
- OIDC-based AWS validation authentication.

Normal CI workflows do not receive cloud deployment or AWS inference permissions.

## 20. API deployment architecture

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

## 21. Frontend deployment architecture

Frontend deployment is manual and validates the production build before publication to Azure Static Web Apps.

The deployment verifies:

- required configuration,
- `npm ci`,
- linting,
- production Vite build,
- compiled API endpoint,
- successful HTTPS response after deployment.

## 22. Runtime verification

Deployment success is not defined only as "the command completed."

The API deployment verifies:

- a new revision was created,
- the new revision is ready,
- the revision uses the expected immutable image,
- `/health/ready` returns successfully,
- the database readiness state is connected.

The frontend deployment verifies:

- the production build exists,
- the expected API URL is compiled into the frontend,
- the deployed site responds over HTTPS,
- the returned page contains the expected React root element.

## 23. Security principles

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
- OIDC instead of stored Azure or AWS long-lived credentials,
- controlled MCP authentication,
- explicit action-execution controls,
- bounded AI review budgets,
- deployment verification and rollback.

## 24. Zero-cost-first strategy

The architecture deliberately avoids making paid cloud infrastructure a requirement for normal development.

The project favors:

- local execution,
- open-source components,
- free tiers where appropriate,
- scale-to-zero compute,
- small dev resource limits,
- targeted cloud validation,
- mock/contract testing for provider failures,
- bounded real model calls,
- manual deployment instead of deploy-on-every-commit.

Cloud usage exists to prove real integration and deployment behavior, not to create a permanent cost dependency.

## 25. Current dev deployment

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

## 26. AWS validation status

AWS Intelligence v1.1 has completed:

```text
GitHub OIDC identity validation          PASS
Bedrock catalog validation               PASS
Bounded real Bedrock inference           PASS
Real CaseMesh second-review path         PASS
Offline fail-safe regression             PASS
Final API/Web/Platform regression         PASS
```

The real CaseMesh application-path validation proved that CaseMesh itself can construct the AWS Bedrock review provider, execute a structured second review, preserve review-budget controls, and return a safe application route without executing privileged business actions.

## 27. Architectural direction

Future work can extend evaluation, observability, FinOps, security automation, and portfolio release assets without changing the core architectural boundaries.

The most important constraint remains unchanged:

**AI capabilities must remain controlled, testable, evidence-grounded, and deployable as normal software rather than treated as an opaque autonomous subsystem.**
