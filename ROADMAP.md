# CaseMesh AI Roadmap

## Roadmap status

CaseMesh AI has moved beyond the original repository-foundation phase.

The current project state includes:

- FastAPI backend,
- PostgreSQL and pgvector integration,
- evidence and retrieval workflows,
- hybrid retrieval,
- structured agentic workflows,
- deterministic tools,
- human-controlled action execution,
- MCP integration,
- React + Vite frontend,
- Microsoft Entra authentication,
- Azure Container Apps deployment,
- Azure Static Web Apps deployment,
- Azure Bicep infrastructure,
- GitHub Actions CI,
- manual API and Web CD,
- GitHub OIDC federation with Azure,
- GHCR immutable image publishing,
- deployment verification and API rollback,
- GitHub Actions supply-chain hardening.

The remaining roadmap focuses on deeper evaluation, observability, optional multi-cloud validation, additional security hardening, and portfolio release polish.

Status legend:

```text
✅ Complete
🟡 In progress / partially complete
⬜ Planned
```

## M0 — Repository Foundation ✅

Completed:

- repository structure,
- architecture documentation,
- contribution and security policies,
- environment verification,
- dataset placement,
- architecture diagrams,
- development documentation,
- project checklist.

## M1 — FastAPI Backend Foundation ✅

Completed:

- Python 3.12 environment,
- FastAPI application,
- settings and configuration,
- structured application setup,
- health endpoints,
- pytest,
- Ruff,
- MyPy,
- Docker-ready API.

## M2 — Domain & Database ✅

Completed:

- PostgreSQL integration,
- SQLAlchemy-based application data access,
- core application entities and services,
- persistence support,
- database-backed API behavior,
- readiness validation for database connectivity.

Further schema evolution can continue as product features grow.

## M3 — Evidence Ingestion ✅

Completed core capability:

- evidence-processing flow,
- input validation,
- parsing support,
- metadata-aware processing,
- integration with investigation workflows.

Future improvements can expand file-type coverage and production-grade storage policies.

## M4 — RAG v1 ✅

Completed:

- document chunking and retrieval foundations,
- embeddings,
- pgvector semantic retrieval,
- evidence-grounded context,
- source-aware retrieval behavior.

## M5 — Hybrid RAG ✅

Completed:

- semantic retrieval,
- PostgreSQL lexical retrieval,
- combined retrieval path,
- ranking and merge behavior,
- grounded context for generation.

Future evaluation work will measure retrieval quality more systematically.

## M6 — Deterministic Tools ✅

Completed tool-oriented capabilities include structured operations such as:

- case retrieval,
- policy retrieval,
- incident or knowledge lookup,
- calculations and deterministic transformations,
- controlled action helpers.

Deterministic code remains preferred over LLM-generated arithmetic or authorization decisions.

## M7 — Structured Agentic Orchestration ✅

Completed:

- structured investigation workflow,
- specialized reasoning responsibilities,
- deterministic steps alongside AI-assisted steps,
- explicit workflow state,
- controlled tool usage.

The project deliberately avoids unnecessary free-form autonomous agents.

## M8 — Local AI MVP ✅

Completed core goals:

- configurable AI provider behavior,
- local-first development support,
- end-to-end investigation workflow,
- provider abstraction at the application level.

The project remains designed so cloud AI is not mandatory for normal development.

## M9 — Human Approval & Controlled Actions ✅

Completed core control model:

- separation between read-side and write-side behavior,
- controlled action execution,
- execution switches and modes,
- live-action allowlisting,
- authorization boundaries around sensitive operations.

Additional product-facing approval UX can continue to evolve.

## M10 — MCP ✅

Completed:

- MCP server,
- MCP client,
- authenticated MCP access,
- structured tool definitions,
- remote transport support,
- stdio transport support,
- MCP integration with investigation workflows,
- controlled external action execution.

## M11 — Evaluation 🟡

Current state:

- automated API tests,
- retrieval and workflow tests,
- MCP tests,
- deterministic behavior checks,
- CI quality gates.

Still planned:

- formal decision-accuracy evaluation,
- retrieval-quality benchmark,
- citation-quality measurement,
- tool-selection evaluation,
- hallucination-rate tracking,
- unauthorized-action-rate measurement,
- repeatable evaluation dataset and reporting.

## M12 — Frontend ✅

Implemented with the current stack:

- React 19,
- Vite,
- TypeScript,
- MSAL authentication,
- production build pipeline,
- Azure Static Web Apps deployment.

The original Next.js plan was replaced by the current React + Vite implementation.

Future work may continue improving product UX and portfolio presentation.

## M13 — Azure Validation ✅

Completed real Azure integration:

- Azure Container Apps for the API,
- Azure Static Web Apps for the frontend,
- Microsoft Entra authentication,
- Azure Bicep,
- GitHub OIDC federation with Azure,
- dev deployment validation,
- runtime health verification.

Current Azure usage is intentionally development/portfolio oriented rather than an always-on production environment.

## M14 — AWS Validation ⬜

Planned optional validation:

- Amazon Bedrock provider integration or targeted proof-of-concept,
- IAM-based authentication,
- cost-controlled validation,
- optional safety/guardrail comparison.

AWS is not required for the current CaseMesh runtime.

## M15 — Optional GCP Validation ⬜

Optional future work:

- targeted Vertex AI validation,
- multimodal experimentation if useful,
- cost-controlled proof-of-concept.

This milestone may be skipped safely if it adds little portfolio or engineering value.

## M16 — Observability & FinOps 🟡

Partially complete:

- structured application behavior,
- deployment logs,
- health and readiness checks,
- CI/CD execution history,
- explicit zero-cost-first architecture decisions.

Still planned:

- OpenTelemetry instrumentation,
- end-to-end tracing,
- provider latency metrics,
- token-usage tracking,
- estimated AI cost tracking,
- Azure monitoring integration where useful,
- budget and cost guardrails.

## M17 — Infrastructure as Code ✅

The original Terraform plan was replaced for the active Azure environment by Azure Bicep.

Completed:

- modular Azure Bicep,
- Container Apps environment definition,
- Container App definition,
- Static Web App definition,
- secure parameters for secrets,
- explicit runtime container image input,
- dev parameterization,
- Bicep compilation in Platform CI.

Future multi-cloud work may use provider-appropriate IaC without changing the current Azure implementation.

## M18 — CI/CD ✅

Completed CI:

- CaseMesh API CI,
- CaseMesh Web CI,
- CaseMesh Platform CI.

Completed CD:

- CaseMesh API Deploy Dev,
- CaseMesh Web Deploy Dev.

Current deployment protections include:

- manual workflow dispatch,
- `main` branch requirement,
- explicit `DEPLOY` confirmation,
- immutable API image tags,
- GHCR publishing,
- Azure OIDC,
- exact Azure Container Apps revision verification,
- API readiness verification,
- API rollback on failed deployment verification,
- frontend build verification,
- post-deployment website verification.

## M19 — Security Hardening 🟡

Completed controls include:

- no committed secrets,
- ignored local environment files,
- safe example configuration,
- secure Bicep secret parameters,
- non-root API container,
- Microsoft Entra authentication,
- HTTPS production API configuration,
- explicit CORS configuration,
- authenticated MCP access,
- controlled action execution,
- least-privilege GitHub Actions permissions,
- GitHub Actions pinned to immutable commit SHAs,
- `persist-credentials: false`,
- Azure OIDC instead of a stored Azure client secret,
- manual deployment confirmation,
- immutable API image references,
- post-deployment verification,
- API rollback.

Still planned or expandable:

- formal threat modeling,
- dependency vulnerability automation,
- rate limiting where appropriate,
- deeper prompt-injection testing,
- formal access reviews,
- production-grade monitoring and incident procedures,
- additional security testing around file ingestion and action execution.

## M20 — Portfolio Release ⬜

Planned final release work:

- final README polish,
- architecture diagrams updated to the final implementation,
- selected screenshots,
- deployment screenshots,
- evaluation results,
- cost and zero-cost-first summary,
- concise demo flow,
- optional demo video or GIF,
- polished GitHub repository presentation,
- final release tag.

## Current delivery baseline

The current validated delivery path is:

```text
Source change
    |
    +--> API CI
    |
    +--> Web CI
    |
    +--> Platform CI
    |
    v
Manual deployment decision
    |
    +--> API Deploy Dev
    |       |
    |       +--> GHCR immutable image
    |       +--> GitHub OIDC -> Azure
    |       +--> Azure Container Apps
    |       +--> exact revision verification
    |       +--> readiness verification
    |       +--> rollback on failure
    |
    +--> Web Deploy Dev
            |
            +--> production Vite build
            +--> Azure Static Web Apps
            +--> production HTTP verification
```

## Current priorities

The next highest-value milestones are:

1. complete formal evaluation and benchmark reporting,
2. expand observability and FinOps,
3. finish remaining security-hardening items,
4. decide whether AWS and GCP validation add enough value to justify the work,
5. prepare the final portfolio release.

## Portfolio release principle

CaseMesh AI should be presented as a complete engineering system, not merely as an AI demo.

The final portfolio release should demonstrate:

- AI engineering,
- RAG,
- agentic workflows,
- MCP,
- backend development,
- frontend integration,
- authentication,
- cloud deployment,
- Infrastructure as Code,
- containerization,
- CI/CD,
- deployment safety,
- security engineering,
- cost-aware architecture.

The project should prefer depth, evidence, and operational credibility over adding technologies only to increase the tool count.
