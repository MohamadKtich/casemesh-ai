# ADR 0004 — Use Hybrid RAG

**Status:** Accepted

## Decision
Combine vector retrieval with PostgreSQL full-text retrieval, merge results, then rerank.

## Why
CaseMesh evidence contains both semantic concepts and exact identifiers, percentages, policy clauses, and incident numbers.

## Trade-off
More retrieval logic than vector-only search, but better recall and factual grounding.
