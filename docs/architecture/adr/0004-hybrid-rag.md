# ADR 0004 — Use Hybrid RAG

**Status:** Accepted, ranking detail superseded by ADR 0010

## Original Decision

Combine vector retrieval with PostgreSQL full-text retrieval, merge results, then rerank.

## Why

CaseMesh evidence contains both semantic concepts and exact identifiers, percentages, policy clauses, and incident numbers.

Hybrid retrieval provides stronger coverage than relying on vector similarity alone.

## Trade-off

Hybrid retrieval introduces more retrieval logic than vector-only search, but improves evidence recall and factual grounding.

## Current Implementation

The core hybrid-retrieval decision remains accepted.

The original generic reranking step was replaced by deterministic Reciprocal Rank Fusion (RRF).

See:

`0010-reciprocal-rank-fusion.md`
