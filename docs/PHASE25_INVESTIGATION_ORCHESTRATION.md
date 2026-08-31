# Phase 25 — Investigation Workflow Orchestration

## Goal

Turn CaseMesh from a grounded RAG API into a persisted investigation workflow
with explicit state, deterministic steps, conditional routing, retry behavior,
grounded findings, and end-to-end evidence traceability.

## Workflow

```text
START
  |
  v
Initialize Run
  |
  v
Analyze Case
  |
  v
Plan Investigation
  |
  v
Retrieve Evidence
  |
  v
Assess Evidence  <-- grounded LLM node
  |
  +-- low/abstain + retry available --> Expand Query --> Retrieve Evidence
  |
  +-- low/abstain + no retry --------> Identify Gaps
  |
  +-- sufficient --------------------> Produce Findings
                                         |
                                         v
                                grounded LLM node
                                         |
                                         v
                                      Finalize
                                         |
                                         v
                                        END
```

## LangGraph

Phase 25 uses LangGraph for orchestration while keeping the business logic in
CaseMesh services and repositories.

The graph uses:

- a typed `InvestigationState`
- deterministic nodes for initialization, planning, retry expansion, and gaps
- conditional routing after evidence assessment
- one configurable retrieval retry
- grounded generation through the existing Phase 24 answer service
- persisted status after each material workflow step

## Persistence

Migration `0004` extends `investigation_runs` with:

- objective
- current step
- retry attempt
- confidence and abstention state
- case analysis
- plan JSON
- retrieved evidence JSON
- assessment
- gaps JSON
- findings
- final citations
- workflow metadata
- error information

The database run ID is the workflow ID.

## Failure behavior

If an API/provider/database error escapes the graph:

1. the workflow is marked `failed`
2. the current step becomes `failed`
3. the error is persisted
4. the API returns the failure instead of pretending the run completed

This phase does not silently execute external actions.

## API

### Start a workflow

```text
POST /cases/{case_id}/investigations
```

Example:

```json
{
  "objective": "Determine whether the customer qualifies for an SLA credit and explain the evidence."
}
```

### Read a workflow

```text
GET /cases/{case_id}/investigations/{workflow_id}
```

### List workflows for a case

```text
GET /cases/{case_id}/investigations
```

## Zero-cost-first

Core orchestration remains local:

- LangGraph runs locally
- PostgreSQL/pgvector runs in Docker
- embeddings run through local Ollama
- generation runs through local `qwen3:8b`

No paid cloud API is required for Phase 25.

## Phase boundary

Phase 25 deliberately does not yet add:

- external MCP actions
- human approval execution gates
- background workers or queues
- distributed checkpoints
- Azure/AWS provider routing
- autonomous customer/account changes

Those remain separate phases so the workflow stays auditable and testable.
