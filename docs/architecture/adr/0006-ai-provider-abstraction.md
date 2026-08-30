# ADR 0006 — Use an AI provider abstraction

**Status:** Accepted

## Decision
Hide provider-specific SDK calls behind a common AIProvider interface.

## Providers
- Ollama
- Azure AI
- AWS Bedrock
- GCP Vertex (optional)

## Why
Supports local development, multi-cloud validation, provider substitution, and lower vendor lock-in.
