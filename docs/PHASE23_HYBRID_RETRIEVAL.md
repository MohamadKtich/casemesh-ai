# Phase 23 — Embeddings + pgvector + Hybrid Retrieval

## Goal

Turn persisted evidence chunks into searchable retrieval context using a
zero-cost-first local embedding provider and PostgreSQL hybrid retrieval.

## Architecture

```text
Document Chunk
   |
   +--> Ollama / nomic-embed-text --> 768-d vector --> pgvector
   |
   +--> PostgreSQL full-text search
                       |
                       v
            Weighted Reciprocal Rank Fusion
                       |
                       v
                Ranked Evidence
```

## Why local Ollama embeddings

The core retrieval path should work without paid cloud inference.

The provider layer is intentionally abstract so Azure or AWS embedding
providers can be added later without changing the retrieval API.

## Embedding model

Default local model:

```text
nomic-embed-text
```

Vector dimension:

```text
768
```

## Database migration 0003

- enables the `vector` PostgreSQL extension
- adds `document_chunks.embedding vector(768)`
- adds embedding metadata
- creates an HNSW cosine index
- creates a PostgreSQL GIN full-text index

## Retrieval strategy

CaseMesh uses two candidate lists:

1. vector similarity from pgvector
2. lexical relevance from PostgreSQL full-text search

The lists are fused with weighted Reciprocal Rank Fusion (RRF), avoiding
fragile assumptions that vector scores and lexical scores share the same
numeric scale.

Default weights:

```text
Vector:  0.65
Keyword: 0.35
```

## Setup

Ensure Docker Desktop and Ollama are running, then:

```powershell
.\scripts\setup_retrieval.ps1
```

The script pulls `nomic-embed-text` only if it is not already installed.

## API

```text
GET  /embeddings/health

POST /cases/{case_id}/documents/{document_id}/embed

POST /cases/{case_id}/retrieval/search
```

Example search body:

```json
{
  "query": "service outage SLA credit",
  "top_k": 5
}
```

## Phase boundary

This phase provides retrieval only.

Generation, citation-aware answer synthesis, LangGraph orchestration,
agent state, tools, human approval, and cloud provider routing remain
separate milestones.
