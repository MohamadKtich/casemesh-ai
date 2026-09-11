# Contributing to CaseMesh AI

## 1. Contribution philosophy

CaseMesh AI is built as a production-oriented engineering project rather than a collection of disconnected experiments.

Contributions should preserve:

- evidence-grounded behavior,
- deterministic logic where possible,
- controlled agentic execution,
- explicit security boundaries,
- reproducible local development,
- zero-cost-first operation,
- testable infrastructure,
- clear CI/CD behavior,
- accurate documentation.

Changes should be small enough to review and focused enough to validate.

## 2. Branching

Use short-lived branches with descriptive names.

Examples:

```text
feature/<short-description>
fix/<short-description>
docs/<short-description>
test/<short-description>
refactor/<short-description>
chore/<short-description>
```

Avoid mixing unrelated concerns into one branch.

## 3. Commit style

Prefer Conventional Commits.

Examples:

```text
feat: add case investigation endpoint
fix: validate evidence MIME type
test: add MCP authorization coverage
docs: update deployment architecture
refactor: simplify retrieval service boundary
ci: harden GitHub Actions supply chain
chore: update dependency metadata
```

Commit messages should describe the purpose of the change, not merely the files modified.

## 4. Pull requests

Every pull request should:

- have a clear and limited scope,
- explain the problem being solved,
- explain the implementation approach,
- include tests when behavior changes,
- update documentation when architecture, deployment, or security behavior changes,
- avoid unrelated formatting or cleanup,
- never include credentials or ignored environment files,
- keep changes compatible with the zero-cost-first development model unless explicitly justified.

Security-sensitive changes require extra review.

## 5. Definition of done

A change is complete when all applicable checks pass.

### API changes

Expected validation includes:

```text
python -m pip check
python -m ruff check src tests
python -m mypy src
python -m pytest -vv
```

### Web changes

Expected validation includes:

```text
npm ci
npm run lint
npm run build
```

### Platform changes

Expected validation includes:

- Docker Compose validation,
- API container build,
- runtime user verification,
- working-directory verification,
- Azure Bicep compilation.

### Documentation changes

Documentation should:

- match the actual implementation,
- avoid describing planned technology as already deployed,
- avoid leaving completed work described as a future milestone,
- use current workflow and resource names,
- avoid exposing secrets or sensitive identifiers.

## 6. GitHub Actions

The repository uses separate workflows for:

- API CI,
- Web CI,
- Platform CI,
- manual API deployment,
- manual Web deployment.

External GitHub Actions are pinned to immutable commit SHAs.

Repository checkout must retain:

```yaml
with:
  persist-credentials: false
```

Do not replace pinned Action SHAs with moving tags such as:

```text
@v4
@v7
@main
```

When updating an Action:

1. resolve the intended upstream version,
2. review the upstream release or commit,
3. obtain the exact commit SHA,
4. update the pinned SHA,
5. keep the readable version comment,
6. run the relevant CI workflow.

CI workflows should keep minimum required permissions.

## 7. Deployment changes

Deployment workflows are intentionally manual.

Do not convert dev deployment into automatic deploy-on-every-commit behavior without a documented reason.

### API deployment

The API deployment contract includes:

- `main` branch requirement,
- explicit `DEPLOY` confirmation,
- immutable GHCR image tag using the Git commit SHA,
- Azure authentication through GitHub OIDC,
- exact revision verification,
- readiness verification,
- exact image verification,
- rollback on failed deployment verification.

Changes must preserve these protections unless the replacement is demonstrably safer.

### Frontend deployment

The web deployment contract includes:

- `main` branch requirement,
- explicit `DEPLOY` confirmation,
- required configuration validation,
- `npm ci`,
- linting,
- production build,
- production API URL verification,
- deployment of prebuilt output,
- post-deployment HTTP verification.

## 8. Secrets and configuration

Never commit:

- `.env`,
- `.env.local`,
- API keys,
- cloud secrets,
- database passwords,
- deployment tokens,
- private certificates,
- real customer data.

Use:

- local ignored environment files for developer secrets,
- GitHub repository variables for non-secret workflow configuration,
- GitHub Secrets for sensitive workflow values,
- secure Bicep parameters for infrastructure secrets.

Do not print secret values in CI logs.

## 9. Azure infrastructure changes

Azure infrastructure is defined with Bicep.

Infrastructure contributions should preserve:

- explicit resource naming,
- secure secret parameters,
- environment-specific parameters,
- independent frontend and API resources,
- minimal dev resource sizing,
- scale-to-zero behavior where supported,
- explicit container image input.

The deployment workflow owns the runtime container image.

Do not reintroduce a stale default image into Bicep.

Run Bicep compilation validation before committing infrastructure changes.

## 10. Container changes

The API container must remain non-root.

Changes to the Dockerfile should preserve:

- expected application working directory,
- non-root runtime user,
- health check behavior,
- reproducible application installation.

Platform CI verifies runtime assumptions.

Any change that causes the container to run as root requires explicit justification and review.

## 11. API changes

API contributions should preserve:

- clear FastAPI route boundaries,
- Pydantic validation,
- typed Python interfaces,
- separation between transport logic and domain logic,
- health and readiness behavior,
- authentication boundaries,
- deterministic authorization for sensitive actions.

Do not move business authorization decisions into LLM prompts.

## 12. Retrieval and RAG changes

Changes to retrieval should consider both semantic and lexical behavior.

When modifying retrieval logic, include relevant tests or evaluation evidence for:

- relevance,
- grounding,
- source traceability,
- metadata preservation,
- ranking behavior.

Avoid replacing deterministic retrieval behavior with model-only selection unless there is strong evidence for doing so.

## 13. Agentic workflow changes

Changes to planning, routing, tools, MCP, or action execution should be treated as security-relevant.

Contributions should preserve:

- explicit workflow state,
- bounded tool access,
- deterministic validation,
- action execution controls,
- safe failure behavior,
- auditability.

Model output must not become an authorization mechanism.

## 14. MCP changes

MCP is used as a controlled integration boundary.

MCP contributions should preserve:

- authenticated access,
- explicit tool schemas,
- separation between read-side and write-side operations,
- application-level authorization,
- clear transport behavior.

New write-side tools require explicit review of authorization and execution controls.

## 15. Frontend changes

The frontend uses React, Vite, TypeScript, and MSAL.

Frontend contributions should preserve:

- authenticated application flow,
- separation between UI and AI/domain logic,
- typed API interaction,
- build-time configuration validation,
- production compatibility with Azure Static Web Apps.

Do not hardcode local-only API URLs into production code.

## 16. Testing expectations

Tests should focus on behavior rather than implementation details where possible.

Important areas include:

- API contracts,
- validation,
- retrieval,
- workflow behavior,
- MCP authorization,
- tool execution,
- URL/configuration conversion,
- error handling,
- deployment assumptions.

Regression tests are expected when fixing bugs.

## 17. Security-sensitive paths

Changes to these areas require extra care:

```text
.github/workflows/
apps/api/Dockerfile
apps/api/src/**/auth*
apps/api/src/**/mcp*
apps/api/src/**/tool*
apps/api/src/**/action*
apps/web/src/auth*
infrastructure/azure/
SECURITY.md
```

This list is not exhaustive.

Any change affecting authentication, authorization, secret handling, deployment, or external actions should be treated as security-sensitive.

## 18. Documentation consistency

Documentation is part of the implementation.

When a feature changes, update the relevant documents in the same contribution when practical.

At minimum, check:

- `README.md`,
- `ARCHITECTURE.md`,
- `SECURITY.md`,
- `CONTRIBUTING.md`,
- `ROADMAP.md`.

Do not leave documentation describing completed implementation as future work.

## 19. Zero-cost-first rule

The default architecture should remain usable without mandatory paid infrastructure.

When proposing a paid or always-on dependency, document:

- why it is needed,
- what free/local alternative was considered,
- expected cost,
- teardown or cost-control behavior,
- whether the dependency is required or optional.

Paid infrastructure must not be introduced casually into the normal contributor path.

## 20. Before committing

Before creating a commit, review:

```text
git status --short
git diff --check
```

Confirm that only intended files changed.

Do not stage local secrets, generated build output, virtual environments, or dependency folders.

## 21. Before pushing

Run the relevant local validation for the files changed.

After pushing to `main` or opening a pull request, verify the applicable GitHub Actions workflows.

A green local run does not replace CI validation.

## 22. Review standard

A contribution is preferred when it is:

- correct,
- secure,
- testable,
- maintainable,
- understandable,
- cost-aware,
- aligned with the existing architecture.

Using more technology is not automatically an improvement.

The goal is to make CaseMesh AI more reliable as a complete software system.
