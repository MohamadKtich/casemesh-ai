# ADR 0005 — Use LangGraph with focused roles

**Status:** Accepted

## Decision
Use LangGraph for orchestration, but do not model every logical role as a fully autonomous LLM agent.

## Roles
- Planner Agent
- Knowledge Node
- Evidence Node
- Policy / Risk Agent
- Resolution Agent

## Why
This reduces cost, latency, hallucinations, and debugging complexity.
