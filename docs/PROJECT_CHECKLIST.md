# CaseMesh AI Project Checklist

This checklist reflects the current repository state rather than the original bootstrap plan.

## Foundation
- [x] Public GitHub repository created
- [x] Repository structure established
- [x] Architecture selected and documented
- [x] Development setup documented
- [x] Security baseline documented
- [x] Contribution guide added
- [x] MIT license added
- [x] Environment examples added
- [x] Architecture diagrams added
- [x] Repository description, topics, and live homepage configured

## Backend and data
- [x] Python 3.12 backend
- [x] FastAPI application
- [x] Health and readiness endpoints
- [x] PostgreSQL integration
- [x] SQLAlchemy and Alembic
- [x] pgvector semantic retrieval
- [x] PostgreSQL Full-Text Search
- [x] Hybrid RAG with Reciprocal Rank Fusion
- [x] Evidence ingestion, parsing, chunking, and metadata
- [x] Citation-aware grounded responses
- [x] Automated API tests
- [x] Ruff and MyPy quality gates
- [x] Dockerized API

## Agentic and governance layer
- [x] Structured investigation workflow
- [x] Deterministic tools
- [x] Policy and risk guardrails
- [x] Human-in-the-loop approval
- [x] Controlled action execution
- [x] Dry-run / disabled-by-default execution posture
- [x] MCP server and client integration
- [x] Authenticated MCP access
- [x] Audit-oriented execution flow

## Evaluation
- [x] Versioned evaluation dataset and artifacts
- [x] Decision / review / credit benchmark metrics
- [x] Repeatability and stability checks
- [x] Failure artifacts and provenance
- [x] Evaluation API exposure
- [x] Interactive evaluation dashboard
- [x] Contextual metric explanations
- [ ] Optional future: deeper retrieval-quality benchmark
- [ ] Optional future: citation-quality measurement
- [ ] Optional future: tool-selection / hallucination tracking

## Frontend
- [x] React 19 + Vite + TypeScript
- [x] Microsoft authentication with MSAL
- [x] Overview workspace
- [x] Cases and case-detail experience
- [x] Evidence workspace
- [x] Investigation storytelling UX
- [x] Approval storytelling UX
- [x] Controlled actions UX
- [x] Evaluation workspace
- [x] Interactive detail drawer
- [x] Dark-only visual system
- [x] Continuous animated network background
- [x] Reduced-motion support
- [x] Production frontend build and linting

## Azure
- [x] Azure Static Web Apps frontend
- [x] Azure Container Apps API
- [x] Microsoft Entra protection
- [x] GitHub OIDC to Azure
- [x] Azure Bicep infrastructure
- [x] GHCR immutable API image publishing
- [x] Readiness verification
- [x] Deployment revision verification
- [x] API rollback behavior
- [x] Live portfolio/dev environment

## AWS Intelligence v1.1
- [x] GitHub OIDC to AWS
- [x] Temporary STS credentials
- [x] Bedrock catalog validation
- [x] Bounded real Bedrock inference
- [x] Real CaseMesh second-review path validation
- [x] Bedrock Guardrails integration
- [x] Temporary S3 staging path
- [x] Textract integration path
- [x] SQS integration path
- [x] SNS escalation path
- [x] Fail-safe / failure-isolation regression
- [x] AWS Intelligence v1.1 release

## CI/CD and platform
- [x] API CI
- [x] Web CI
- [x] Platform CI
- [x] Manual API deployment workflow
- [x] Manual Web deployment workflow
- [x] AWS validation workflows
- [x] Final full-regression workflow
- [x] Immutable GitHub Actions pinning
- [x] Least-privilege workflow permissions

## Portfolio close-out
- [x] README aligned with actual implementation
- [x] Architecture documentation aligned
- [x] Security and contribution documentation aligned
- [x] Zero-cost-first strategy documented
- [x] Portfolio demo flow documented
- [x] Repository description/topics/homepage configured
- [ ] Add selected final UI screenshots
- [ ] Optional: add one deployment/validation screenshot or short demo GIF
- [ ] Run final release regression on release commit
- [ ] Publish next final portfolio release/tag

## Post-portfolio optional work
These items are deliberately not blockers for considering CaseMesh a complete portfolio engineering project.

- [ ] OpenTelemetry and end-to-end tracing
- [ ] Provider latency / token / cost aggregation
- [ ] Richer FinOps dashboarding
- [ ] Formal threat model and deeper prompt-injection testing
- [ ] Broader dependency/security automation
- [ ] Optional GCP validation
