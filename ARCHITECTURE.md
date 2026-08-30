# CaseMesh AI Architecture

## 1. Architecture goal

CaseMesh AI is designed as a full-stack, local-first, multi-provider AI application for evidence-grounded case investigation and resolution.

The architecture favors:
- reliability over agent count,
- deterministic tools over LLM arithmetic,
- traceability over opaque reasoning,
- staged cloud usage over always-on cloud infrastructure,
- provider abstraction over vendor lock-in.

## 2. Application layers

### Web layer
**Next.js + TypeScript**

Responsibilities:
- dashboard,
- case creation,
- evidence upload UI,
- investigation status,
- cited findings,
- approval UI,
- audit and cost views.

AI logic does not live in the frontend.

### API layer
**FastAPI**

Responsibilities:
- API contracts,
- authentication integration,
- validation,
- case management,
- evidence ingestion,
- workflow execution requests,
- approval endpoints,
- results retrieval.

### Domain layer
Core domain concepts:
- User
- Case
- CaseDocument
- Evidence
- Policy
- InvestigationRun
- ResolutionDraft
- Approval
- ActionRequest
- AuditEvent
- ProviderCall
- CostRecord

The LLM is not the system of record.

## 3. Data architecture

### PostgreSQL
Primary transactional database.

### pgvector
Semantic retrieval inside PostgreSQL.

### PostgreSQL Full-Text Search
Lexical / keyword retrieval.

### MinIO
Local evidence object storage.

### Azure Blob Storage
Cloud evidence storage during validation / deployment.

## 4. Hybrid RAG

Retrieval path:

```text
Query
  ├── Vector Search (pgvector)
  └── Keyword Search (PostgreSQL FTS)
          ↓
        Merge
          ↓
       Rerank
          ↓
Best Evidence + Metadata
          ↓
LLM Synthesis + Citations
```

Returned evidence should retain:
- source_id,
- document_id,
- page / section where applicable,
- chunk_id,
- retrieval score,
- metadata needed for audit.

## 5. Orchestration model

CaseMesh uses five logical roles, but deliberately avoids making every role a free-form autonomous agent.

### Planner Agent
LLM-oriented orchestration role.

### Knowledge Node
RAG + tools. Focuses on contracts, policies, internal knowledge, and citations.

### Evidence Node
Uses deterministic tools first. AI is used selectively for unstructured evidence.

### Policy / Risk Agent
Rules + grounded LLM reasoning.

### Resolution Agent
Synthesizes findings into a structured recommendation.

Benefits:
- lower cost,
- lower latency,
- easier debugging,
- fewer hallucinations,
- better operational control.

## 6. Deterministic tools

Examples:
- calculate_uptime
- calculate_service_credit
- retrieve_case
- retrieve_policy
- get_incident
- search_contract

Calculations and deterministic transformations stay in code.

## 7. Human approval

Read-only operations may run automatically.

Write-side, financial, or high-impact actions require approval.

```text
Resolution Draft
      ↓
Pending Approval
   ↙   ↓    ↘
Approve Changes Reject
   ↓
MCP Gateway
   ↓
Business Action
```

## 8. MCP

MCP is reserved for standardized external / business integrations rather than every internal Python function.

Examples:
- get_case
- add_case_note
- update_case_status
- create_credit_request

## 9. AI provider abstraction

```text
AIProvider
├── OllamaProvider
├── AzureProvider
├── BedrockProvider
└── VertexProvider (optional)
```

Provider roles:
- Ollama: local development.
- Azure AI: primary cloud reasoning.
- AWS Bedrock: secondary provider / safety-oriented validation.
- GCP Vertex: optional multimodal capability.

GCP is not a runtime dependency.

## 10. Deployment strategy

### Phase 1 — Local development
- Docker
- Next.js
- FastAPI
- PostgreSQL + pgvector
- MinIO
- LangGraph
- Ollama

### Phase 2 — Cloud validation
Enable only required cloud services and run targeted tests.

### Phase 3 — Final demo / production-lite
Keep only resources needed for the final deployed demo.

## 11. Observability

Application instrumentation will use OpenTelemetry.

Tracked dimensions include:
- case_id,
- trace_id,
- provider,
- model,
- agent / node,
- tool,
- latency,
- tokens,
- errors,
- estimated cost.

## 12. Cost governance

CaseMesh will maintain internal estimated cost records for model calls.

Planned guardrails:
- max LLM calls per case,
- max tokens per case,
- max estimated cost per case,
- provider-specific usage logging,
- cloud budget alerts.

## 13. Security principles

- no secrets in Git,
- `.env` ignored,
- `.env.example` contains placeholders only,
- least privilege,
- validation of uploaded evidence,
- tool authorization boundaries,
- approval before sensitive actions,
- audit logging,
- prompt-injection defenses at retrieval/tool boundaries.

## 14. CI/CD principle

Every PR:
- lint,
- type checks,
- unit tests,
- integration tests,
- security checks,
- small AI evaluation subset.

Before release:
- full evaluation dataset,
- manual approval,
- deployment.
