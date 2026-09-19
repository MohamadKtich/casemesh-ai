# ADR 0010 — Use Reciprocal Rank Fusion for Hybrid Retrieval

**Status:** Accepted

## Context

CaseMesh AI retrieves evidence through two complementary retrieval paths:

- semantic vector retrieval with pgvector,
- lexical retrieval with PostgreSQL Full-Text Search.

These retrieval methods produce independently ranked result sets.

The system needs a deterministic way to combine them without introducing an additional AI reranking dependency.

## Decision

Use Reciprocal Rank Fusion (RRF) to combine semantic and lexical retrieval rankings.

The retrieval pipeline is:

```text
Query
  |
  +--> pgvector semantic retrieval
  |
  +--> PostgreSQL Full-Text Search
  |
  v
Reciprocal Rank Fusion (RRF)
  |
  v
Ranked Evidence
  |
  v
Grounded Context
```

## Why

RRF provides:

- deterministic ranking fusion,
- no additional LLM call,
- no dedicated cross-encoder dependency,
- predictable behavior,
- straightforward testing,
- low operational cost,
- preservation of both semantic and lexical retrieval signals.

## Consequences

- semantic and lexical searches remain independently useful,
- their ranked outputs are fused before grounded generation,
- retrieval ranking is reproducible and testable,
- CaseMesh does not require an AI reranker in the current architecture.

## Supersedes

This ADR supersedes only the generic reranking detail in ADR 0004.

The broader ADR 0004 decision to use Hybrid RAG remains accepted.
