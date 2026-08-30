# ADR 0003 — Use PostgreSQL + pgvector

**Status:** Accepted

## Decision
Use PostgreSQL as the system of record and pgvector for semantic search.

## Why
- transactions
- JSON support
- vector search
- full-text search
- one primary data platform instead of multiple databases

## Trade-off
A dedicated vector database may outperform it at very large scale, which is unnecessary for the current project.
