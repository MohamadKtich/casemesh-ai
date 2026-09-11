# Security Policy

## 1. Security posture

CaseMesh AI is designed with layered security controls across source control, CI/CD, identity, containers, API access, MCP integration, infrastructure, and deployment.

The project follows these principles:

- never commit secrets,
- prefer identity-based authentication over long-lived credentials,
- apply least privilege,
- keep sensitive actions behind explicit authorization controls,
- separate CI from deployment permissions,
- verify deployments after they complete,
- make rollback behavior explicit,
- treat AI output as untrusted until validated by application rules.

## 2. Repository rules

Never commit:

- `.env`,
- `.env.local`,
- access keys,
- API keys,
- cloud client secrets,
- private certificates,
- database passwords,
- raw deployment tokens,
- personally identifiable data that is not explicitly approved for the repository,
- real customer data,
- production credentials.

Safe example configuration files may be committed only when they contain placeholders or non-sensitive public identifiers.

The repository intentionally ignores local environment files, virtual environments, build output, and dependency directories.

## 3. Secret handling

Secrets must be supplied through secure runtime or deployment mechanisms.

Current patterns include:

- GitHub Secrets for sensitive CI/CD values,
- GitHub repository variables for non-secret configuration,
- secure Bicep parameters for infrastructure secrets,
- local ignored environment files for developer-only secrets,
- Azure Container Apps secret references for runtime secret injection.

Secrets must not be echoed to logs.

When testing secret-related workflows, display only secret names or redacted values.

## 4. GitHub Actions security

The active GitHub Actions workflows use a hardened configuration.

Controls include:

- external Actions pinned to full immutable commit SHAs,
- `persist-credentials: false` on repository checkout,
- explicit workflow permissions,
- read-only `contents` access for CI workflows,
- `packages: write` only where GHCR publishing is required,
- `id-token: write` only where Azure OIDC authentication is required,
- manual deployment workflows instead of automatic cloud deployment on every commit,
- explicit `DEPLOY` confirmation for dev deployments.

CI workflows must not receive deployment permissions unless a concrete need is documented.

## 5. Azure authentication

API deployment to Azure uses GitHub OIDC federation.

This avoids storing an Azure client secret in GitHub.

The GitHub deployment identity is intended for the Azure dev environment and is scoped to the required Azure resource group.

Non-secret Azure identifiers are stored as repository variables.

Long-lived Azure credentials should not be introduced unless there is no safer supported alternative.

## 6. GitHub Container Registry

The API image is published to GHCR by the API deployment workflow.

Images use immutable Git commit SHA tags.

Example:

```text
ghcr.io/mohamadktich/casemesh-api:<git-sha>
```

Mutable deployment tags such as `latest` are intentionally avoided for deployment verification.

The workflow verifies that the exact expected image is the image used by the ready Azure Container Apps revision.

## 7. Container security

The API container is configured to run as a non-root user.

Platform CI verifies:

- the expected runtime user,
- the expected working directory,
- successful image build.

The Dockerfile includes an application health check.

Container runtime changes that reintroduce root execution require explicit review.

## 8. Application authentication

The deployed application uses Microsoft Entra ID.

The frontend uses MSAL for user authentication.

Azure Container Apps authentication protects API access.

Authentication configuration is separated from the application source code through deployment configuration.

Operational health endpoints remain available for deployment readiness checks.

## 9. API transport security

Production frontend configuration must use an HTTPS API endpoint.

Azure Container Apps ingress is configured to reject insecure transport.

CORS origins are explicitly configured.

Changes that broaden CORS access should be reviewed carefully.

## 10. MCP security

MCP is treated as a controlled integration boundary.

Security controls include:

- MCP authentication,
- explicit tool definitions,
- application-level action controls,
- execution-mode configuration,
- allowlisted live actions,
- separation between read-side and write-side behavior.

An AI model response by itself must not grant permission to execute a sensitive business action.

Tool calls must remain subject to deterministic authorization and validation.

## 11. AI and agent controls

Agentic behavior is intentionally constrained.

The architecture requires:

- explicit permissions,
- deterministic validation for sensitive operations,
- tool allowlists,
- controlled execution modes,
- prompt-injection-aware retrieval and tool boundaries,
- auditable action paths,
- application-level authorization outside the model.

LLM output is treated as untrusted input until validated.

## 12. Evidence and file handling

Evidence-processing features should validate:

- MIME type,
- file extension,
- file size,
- allowed formats,
- malformed input,
- filenames,
- parsing failures.

Private, customer, or sensitive source material should not be added to the repository.

Synthetic or approved test data should be preferred for development and portfolio demonstrations.

## 13. Infrastructure secrets

Azure infrastructure is defined with Bicep.

Sensitive infrastructure inputs are declared with `@secure()`.

Secret values are passed into Azure Container Apps secret configuration and referenced from application environment variables.

Do not replace secure parameters with plain string parameters for sensitive values.

## 14. Deployment safety

Cloud deployment is intentionally manual.

### API deployment

The API workflow requires:

- `main` branch,
- explicit `DEPLOY` confirmation,
- immutable image publication,
- OIDC authentication,
- exact revision verification,
- readiness verification,
- exact image verification.

If post-deployment verification fails after an update, the workflow attempts rollback to the previous image and verifies the rollback revision.

### Frontend deployment

The web workflow requires:

- `main` branch,
- explicit `DEPLOY` confirmation,
- required deployment configuration,
- linting,
- production build,
- verification of the compiled API URL,
- post-deployment HTTP verification.

## 15. Health and readiness

Deployment success is not defined only by a successful CLI command.

The API readiness endpoint is:

```text
/health/ready
```

The deployment workflow verifies that the endpoint responds successfully after the exact expected Azure revision becomes ready.

Readiness includes database connectivity state.

## 16. Supply-chain changes

Changes to any of the following require additional review:

- `.github/workflows/`,
- Dockerfiles,
- dependency manifests,
- lock files,
- Azure Bicep,
- authentication configuration,
- MCP authorization logic,
- deployment scripts,
- secret handling.

When updating a pinned GitHub Action, resolve and review the new upstream commit SHA before replacing the existing pin.

## 17. Dependency and code quality controls

Current CI quality gates include:

- Python dependency validation,
- Ruff,
- MyPy,
- pytest,
- `npm ci`,
- Oxlint,
- production web build,
- Docker image build,
- Bicep compilation.

Security-sensitive changes should not bypass these gates.

## 18. Zero-cost-first security considerations

The project follows a zero-cost-first strategy without weakening core security controls.

Cost reduction must not justify:

- committing secrets,
- disabling authentication,
- using broad cloud permissions,
- removing deployment verification,
- running containers as root,
- exposing write-side actions without authorization.

Free-tier or local alternatives are preferred only when they preserve the required security boundary.

## 19. Incident response

If a secret is accidentally exposed:

1. revoke or rotate it immediately,
2. remove it from active configuration,
3. replace it in the relevant secret store,
4. assess repository and workflow logs for exposure,
5. remove the value from Git history if necessary,
6. verify that deployments still use the rotated credential,
7. document the incident privately.

Deleting a secret from the latest commit alone is not sufficient if it remains in Git history.

## 20. Security reporting

Do not publish sensitive vulnerability details, active credentials, or exploitable deployment information in public issues.

Use a private reporting channel when one is available for the repository.

Until a dedicated disclosure channel is published, security-sensitive findings should be shared privately with the repository owner.

## 21. Scope note

This repository contains a development and portfolio-oriented cloud environment.

The Azure dev deployment is not presented as a production SLA environment.

Production use would require additional controls appropriate to the deployment context, such as formal incident response, monitoring, vulnerability management, access review, backup policy, and organization-specific governance.
