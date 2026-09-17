# CaseMesh AI Roadmap

## Roadmap status

CaseMesh AI has moved beyond the original repository-foundation phase and now has a validated multi-cloud engineering baseline.

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
- GitHub Actions supply-chain hardening,
- AWS Intelligence v1.1 integration,
- GitHub OIDC federation with AWS,
- bounded real Bedrock inference validation,
- real CaseMesh Bedrock second-review validation,
- offline AWS fail-safe regression,
- final full regression across API, Web, Platform, Docker, and Bicep.

The remaining roadmap focuses on deeper evaluation, observability, FinOps, additional security automation, and final portfolio-release polish.

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
- authorization boundaries around sensitive operations,
- PolicyGuard authority outside model output,
- human approval routing for high-risk and financial actions.

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
- second-review and policy-safety tests,
- cross-cloud failure-isolation tests,
- final full-regression workflow,
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

## M14 — AWS Validation ✅

Completed AWS Intelligence v1.1 validation:

- AWS client and gateway abstraction,
- temporary S3 staging and lifecycle logic,
- Textract document-intelligence adapters,
- SQS asynchronous completion path,
- Bedrock second-review provider,
- Bedrock Guardrails integration,
- risk-trigger routing,
- SNS escalation alerts,
- request timeouts and bounded review budgets,
- idempotency and replay behavior,
- cross-cloud failure isolation,
- safe API/UI summary behavior,
- federated identity support and refresh testing,
- GitHub OIDC federation with AWS IAM,
- Bedrock catalog validation,
- bounded real Bedrock inference,
- real CaseMesh second-review application-path validation,
- offline fail-safe regression,
- final full regression after integration.

AWS remains optional for normal development and is not required for the core CaseMesh runtime.

See `docs/AWS_INTELLIGENCE_V1_1.md` for the validation record.

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
- bounded AWS model validation,
- second-review budget controls,
- explicit zero-cost-first architecture decisions.

Still planned:

- OpenTelemetry instrumentation,
- end-to-end tracing,
- provider latency metrics,
- token-usage aggregation,
- estimated AI cost tracking,
- Azure monitoring integration where useful,
- broader budget/cost dashboards.

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

Completed manual validation gates:

- CaseMesh AWS OIDC Validate,
- CaseMesh AWS Bedrock Catalog Validate,
- CaseMesh AWS Bedrock Inference Validate,
- CaseMesh AWS Application Path Validate,
- CaseMesh AWS Safety Validate,
- CaseMesh Final Full Regression.

Current deployment protections include:

- manual workflow dispatch,
- `main` branch requirement,
- explicit confirmation values,
- immutable API image tags,
- GHCR publishing,
- Azure OIDC,
- AWS OIDC for validation,
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
- PolicyGuard authority outside AI output,
- least-privilege GitHub Actions permissions,
- GitHub Actions pinned to immutable commit SHAs,
- `persist-credentials: false`,
- Azure OIDC instead of a stored Azure client secret,
- AWS OIDC instead of static AWS access keys for validation,
- manual deployment and validation confirmation,
- immutable API image references,
- post-deployment verification,
- API rollback,
- provider/guardrail failure fail-closed behavior,
- cross-cloud alert-failure isolation,
- safe metadata exposure controls.

Still planned or expandable:

- formal threat modeling,
- dependency vulnerability automation,
- rate limiting where appropriate,
- deeper prompt-injection testing,
- formal access reviews,
- production-grade monitoring and incident procedures,
- additional security testing around file ingestion and action execution.

## M20 — Portfolio Release 🟡

Completed release-preparation work:

- core README reflects the validated architecture,
- architecture documentation includes AWS Intelligence v1.1,
- AWS validation record documented,
- final full-regression workflow validated.

Still planned:

- architecture diagrams updated to the final implementation,
- selected screenshots,
- deployment and validation screenshots,
- evaluation results,
- concise cost/zero-cost-first summary,
- concise demo flow,
- optional demo video or GIF,
- polished GitHub repository presentation,
- final release tag.

## Current delivery baseline

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

Optional/manual AWS validation
    |
    +--> GitHub OIDC -> AWS
    +--> Bedrock catalog/inference
    +--> real CaseMesh second-review path
    +--> offline safety regression
```

## Current priorities

The next highest-value milestones are:

1. complete formal evaluation and benchmark reporting,
2. expand observability and FinOps,
3. finish remaining security-hardening items,
4. prepare architecture diagrams and portfolio media,
5. create the final portfolio release/tag.

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
- Azure deployment,
- AWS cross-cloud intelligence validation,
- Infrastructure as Code,
- containerization,
- CI/CD,
- deployment safety,
- security engineering,
- cost-aware architecture.

The project should prefer depth, evidence, and operational credibility over adding technologies only to increase the tool count.
