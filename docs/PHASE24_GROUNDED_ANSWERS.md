# Phase 24 — Grounded Answer Synthesis + Evidence Citations

## Goal

Turn Phase 23 ranked evidence into a constrained answer that cites the exact
retrieved evidence chunks used by the local model.

## Runtime path

```text
Question
  |
  +--> Phase 23 Hybrid Retrieval
  |       |
  |       +--> pgvector semantic candidates
  |       +--> PostgreSQL lexical candidates
  |       +--> weighted RRF
  |
  +--> Evidence Context Builder
  |       |
  |       +--> [E1], [E2], ... stable source labels
  |       +--> context-size limits
  |
  +--> Local Generation Provider
          |
          +--> Ollama
          +--> qwen3:8b
          +--> JSON-only output
          +--> thinking disabled
          |
          v
     Grounding Validator
          |
          +--> rejects unknown citation labels
          +--> rejects uncited non-abstained answers
          +--> one repair attempt
          |
          v
     Answer + structured citations
```

## Zero-cost-first design

The default generation provider is local Ollama with `qwen3:8b`.
No paid Azure, AWS, Google, or hosted LLM API is required for the core path.

The generation provider protocol is intentionally separate from Ollama so
cloud providers can be added later without changing the answer API.

## Grounding contract

The model receives only retrieved evidence and is instructed to:

- answer from supplied evidence only
- cite factual sentences with `[E1]`, `[E2]`, etc.
- never invent citation labels
- abstain when evidence is insufficient
- return JSON with `answer`, `confidence`, and `abstained`

CaseMesh validates the response before returning it.

## API

### Generation health

```text
GET /generation/health
```

### Grounded answer

```text
POST /cases/{case_id}/answers
```

Example body:

```json
{
  "question": "What evidence supports the customer's SLA credit request?",
  "top_k": 5
}
```

The response includes:

- grounded answer text
- inline evidence labels
- structured chunk/document citations
- confidence
- abstention flag
- retrieval metadata
- grounding coverage metadata
- embedding and generation model names

## Phase boundary

This phase generates grounded answers but does not yet implement:

- LangGraph investigation workflows
- persistent agent state
- MCP tool execution
- human approval gates for external actions
- cloud model routing
- evaluation dashboards
