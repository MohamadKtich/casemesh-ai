# Phase 26 — Human-in-the-Loop Approval + Policy Guardrails

## Goal

Add a real governance boundary between AI recommendations and sensitive actions.

Phase 26 does **not** execute external actions. It creates governed action
requests, evaluates them with deterministic policy rules, pauses sensitive
requests for human approval, durably checkpoints the LangGraph state in
PostgreSQL, and records audit events.

## Architecture

```text
Completed Investigation
        |
        v
Proposed Action
        |
        v
Deterministic Policy Guard
        |
        +----------------------------+
        |                            |
        | block                      | allow
        v                            v
    BLOCKED                    AUTO-APPROVED
        |                            |
        |                            |
        +-----------+----------------+
                    |
                    | require_approval
                    v
          LangGraph Human Review
                    |
              interrupt(...)
                    |
                    v
       PostgreSQL durable checkpoint
                    |
          waits for human decision
                    |
            +-------+-------+
            |               |
         approve          reject
            |               |
            v               v
         APPROVED        REJECTED

External execution: DISABLED in Phase 26
```

## Why durable checkpoints

A human approval can take minutes, hours, or days. The graph therefore uses
`langgraph-checkpoint-postgres` instead of in-memory persistence.

The action request ID becomes a stable LangGraph thread ID:

```text
action:<action_request_uuid>
```

The graph can be resumed with the same thread after the API process restarts.

## Deterministic policy rules

### `issue_sla_credit`

- risk: critical
- requires valid `credit_percent`
- blocks low-confidence, abstained, or uncited investigations
- otherwise requires explicit human approval

### `send_customer_notification`

- risk: high
- blocks abstained or uncited investigations
- otherwise requires human approval

### `update_case_status`

- risk: high
- requires a non-empty target status
- always requires human approval

### `create_internal_note`

- risk: low
- allowed without review by default
- still does not execute an external action in Phase 26

### Unknown actions

Denied by default.

## Human review

The approval graph uses LangGraph `interrupt()`.

The interrupt payload exposes:

- action request ID
- action type
- risk level
- policy rationale
- proposed payload
- allowed decisions
- an explicit notice that external execution is still disabled

The resume endpoint accepts:

```json
{
  "decision": "approve",
  "reviewer_ref": "reviewer-demo",
  "comment": "Reviewed evidence and approved."
}
```

## API

### Propose a governed action

```text
POST /cases/{case_id}/investigations/{workflow_id}/actions
```

### Resume with a human decision

```text
POST /cases/{case_id}/actions/{action_request_id}/decision
```

### Read an action

```text
GET /cases/{case_id}/actions/{action_request_id}
```

### List case actions

```text
GET /cases/{case_id}/actions
```

### Read audit trail

```text
GET /cases/{case_id}/actions/{action_request_id}/audit-events
```

## Recommended validation

### Test A — policy blocks unsafe financial action

Use the existing low-confidence investigation:

```json
{
  "action_type": "issue_sla_credit",
  "payload": {
    "credit_percent": 10
  }
}
```

Expected:

```text
status = blocked
policy.decision = block
risk_level = critical
execution_enabled = false
```

### Test B — HITL interrupt

Use:

```json
{
  "action_type": "update_case_status",
  "payload": {
    "status": "resolved"
  }
}
```

Expected:

```text
status = awaiting_approval
policy.decision = require_approval
interrupt.type = human_approval_required
```

Restart the API server before the next step if you want to prove durable
checkpoint recovery.

Then approve:

```json
{
  "decision": "approve",
  "reviewer_ref": "reviewer-demo",
  "comment": "Reviewed and approved."
}
```

Expected:

```text
status = approved
execution_enabled = false
```

The approval is authorization only. Phase 27 can attach MCP-based external
execution behind this approval boundary.
