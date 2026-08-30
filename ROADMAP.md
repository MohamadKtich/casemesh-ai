# CaseMesh AI Roadmap

## M0 — Repository Foundation ✅
- Repository structure
- Architecture documentation
- ADRs
- GitHub templates
- Environment verification
- Dataset placement
- Security baseline
- Architecture diagrams

## M1 — FastAPI Backend Foundation
- Python 3.12 virtual environment
- FastAPI app
- settings/configuration
- structured logging
- `/health`
- pytest
- Ruff
- mypy
- initial Dockerfile

## M2 — Domain & Database
- PostgreSQL
- SQLAlchemy
- Alembic
- core entities
- migrations
- CRUD
- repository/service layers

## M3 — Evidence Ingestion
- file upload
- file validation
- MinIO
- parsing
- metadata
- ingestion status

## M4 — RAG v1
- chunking
- embeddings
- pgvector
- semantic retrieval
- citations

## M5 — Hybrid RAG
- PostgreSQL FTS
- semantic + lexical retrieval
- merge
- rerank
- retrieval evaluation

## M6 — Deterministic Tools
- uptime calculator
- service-credit calculator
- case retrieval
- policy retrieval
- incident lookup

## M7 — LangGraph Orchestration
- Planner Agent
- Knowledge Node
- Evidence Node
- Policy / Risk Agent
- Resolution Agent
- structured state

## M8 — Local AI MVP
- AIProvider abstraction
- Ollama provider
- Qwen3 8B
- complete local workflow
- local evaluation

## M9 — Human Approval
- pending approval state
- approve
- reject
- request changes
- audit events

## M10 — MCP
- MCP gateway
- case-management tools
- write-side authorization
- approved action execution

## M11 — Evaluation
- decision accuracy
- retrieval accuracy
- citation accuracy
- calculation accuracy
- tool selection accuracy
- hallucination rate
- unauthorized action rate

## M12 — Frontend
- Next.js
- TypeScript
- dashboard
- case pages
- investigation view
- approval UI
- audit / cost views

## M13 — Azure Validation
- Azure AI
- Blob Storage
- Container Apps
- Key Vault
- Application Insights

## M14 — AWS Validation
- Amazon Bedrock
- Bedrock Guardrails
- IAM

## M15 — Optional GCP Validation
- Vertex AI multimodal
- skip safely if unavailable

## M16 — Observability & FinOps
- OpenTelemetry
- traces
- token/cost tracking
- budgets / alerts

## M17 — Infrastructure as Code
- Terraform
- plan/apply/destroy
- cloud teardown workflow

## M18 — CI/CD
- GitHub Actions
- test gates
- small PR evaluations
- release evaluation
- manual deployment approval

## M19 — Security Hardening
- secrets
- auth
- RBAC
- prompt injection defenses
- file validation
- rate limits
- MCP permissions

## M20 — Portfolio Release
- final demo
- screenshots
- README polish
- architecture diagrams
- evaluation results
- cost breakdown
- demo video / GIF
- v1.0 release
