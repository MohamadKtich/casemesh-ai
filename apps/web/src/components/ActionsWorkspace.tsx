import {
  useEffect,
  useState,
} from "react"

import {
  executeAction,
  getAction,
  getActionAuditEvents,
  getActions,
  type ActionExecutionResponse,
  type ActionRequestRecord,
  type AuditEventRecord,
  type CaseRecord,
} from "../lib/api"


interface ActionsWorkspaceProps {
  caseRecord: CaseRecord
  onBack: () => void
}


function formatDate(
  value: string,
): string {
  return new Date(
    value,
  ).toLocaleString()
}


function formatJson(
  value: Record<string, unknown>,
): string {
  return JSON.stringify(
    value,
    null,
    2,
  )
}


function canDryRun(
  action: ActionRequestRecord,
): boolean {
  return (
    action.status === "approved" ||
    action.status === "auto_approved"
  )
}


function ActionsWorkspace({
  caseRecord,
  onBack,
}: ActionsWorkspaceProps) {
  const [
    actions,
    setActions,
  ] = useState<ActionRequestRecord[]>([])

  const [
    selectedAction,
    setSelectedAction,
  ] = useState<ActionRequestRecord | null>(
    null,
  )

  const [
    auditEvents,
    setAuditEvents,
  ] = useState<AuditEventRecord[]>([])

  const [
    executionResult,
    setExecutionResult,
  ] = useState<ActionExecutionResponse | null>(
    null,
  )

  const [
    loading,
    setLoading,
  ] = useState(true)

  const [
    loadingAudit,
    setLoadingAudit,
  ] = useState(false)

  const [
    executing,
    setExecuting,
  ] = useState(false)

  const [
    requestedBy,
    setRequestedBy,
  ] = useState(
    "frontend-operator",
  )

  const [
    idempotencyKey,
    setIdempotencyKey,
  ] = useState("")

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  )

  const [
    statusMessage,
    setStatusMessage,
  ] = useState<string | null>(
    null,
  )


  useEffect(() => {
    const controller =
      new AbortController()

    async function loadActions() {
      try {
        setLoading(true)

        const data =
          await getActions(
            caseRecord.id,
            controller.signal,
          )

        setActions(data)

        const executable =
          data.find(
            (action) =>
              action.status === "approved" ||
              action.status === "auto_approved",
          )

        const first =
          executable ??
          data[0] ??
          null

        setAuditEvents([])

        setSelectedAction(
          first,
        )

        if (first) {
          setIdempotencyKey(
            `frontend-dryrun-${first.action_request_id}`,
          )
        }

        setError(null)
      } catch (loadError) {
        if (
          loadError instanceof DOMException &&
          loadError.name === "AbortError"
        ) {
          return
        }

        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load action requests.",
        )
      } finally {
        setLoading(false)
      }
    }

    void loadActions()

    return () => {
      controller.abort()
    }
  }, [caseRecord.id])


  useEffect(() => {
    if (!selectedAction) {
      return
    }

    const actionRequestId =
      selectedAction.action_request_id

    const controller =
      new AbortController()

    async function loadAudit() {
      try {
        setLoadingAudit(true)

        const events =
          await getActionAuditEvents(
            caseRecord.id,
            actionRequestId,
            controller.signal,
          )

        setAuditEvents(
          events,
        )
      } catch (auditError) {
        if (
          auditError instanceof DOMException &&
          auditError.name === "AbortError"
        ) {
          return
        }

        setError(
          auditError instanceof Error
            ? auditError.message
            : "Unable to load action audit history.",
        )
      } finally {
        setLoadingAudit(false)
      }
    }

    void loadAudit()

    return () => {
      controller.abort()
    }
  }, [
    caseRecord.id,
    selectedAction,
  ])


  function selectAction(
    action: ActionRequestRecord,
  ) {
    setAuditEvents([])

    setSelectedAction(
      action,
    )

    setIdempotencyKey(
      `frontend-dryrun-${action.action_request_id}`,
    )

    setExecutionResult(
      null,
    )

    setStatusMessage(
      null,
    )

    setError(
      null,
    )
  }


  async function refreshSelectedAction(
    actionRequestId: string,
  ) {
    const refreshed =
      await getAction(
        caseRecord.id,
        actionRequestId,
      )

    setSelectedAction(
      refreshed,
    )

    setActions(
      (current) =>
        current.map(
          (action) =>
            action.action_request_id ===
            refreshed.action_request_id
              ? refreshed
              : action,
        ),
    )

    const events =
      await getActionAuditEvents(
        caseRecord.id,
        actionRequestId,
      )

    setAuditEvents(
      events,
    )
  }


  async function handleDryRun() {
    if (!selectedAction) {
      return
    }

    if (!canDryRun(selectedAction)) {
      setError(
        "Only approved or auto-approved actions can be simulated.",
      )

      return
    }

    const cleanRequestedBy =
      requestedBy.trim()

    const cleanIdempotencyKey =
      idempotencyKey.trim()

    if (cleanRequestedBy.length < 2) {
      setError(
        "Requested-by reference must contain at least two characters.",
      )

      return
    }

    if (cleanIdempotencyKey.length < 8) {
      setError(
        "Idempotency key must contain at least eight characters.",
      )

      return
    }

    const actionRequestId =
      selectedAction.action_request_id

    try {
      setExecuting(true)
      setError(null)
      setExecutionResult(null)

      setStatusMessage(
        "Running controlled dry-run simulation...",
      )

      const result =
        await executeAction(
          caseRecord.id,
          actionRequestId,
          "dry_run",
          cleanIdempotencyKey,
          cleanRequestedBy,
        )

      setExecutionResult(
        result,
      )

      await refreshSelectedAction(
        actionRequestId,
      )

      setStatusMessage(
        result.status === "replayed"
          ? "Dry-run replay completed safely."
          : "Dry-run simulation completed successfully.",
      )
    } catch (executionError) {
      setStatusMessage(
        null,
      )

      setError(
        executionError instanceof Error
          ? executionError.message
          : "Dry-run execution failed.",
      )
    } finally {
      setExecuting(false)
    }
  }


  const executableCount =
    actions.filter(
      canDryRun,
    ).length


  return (
    <section className="evidence-workspace">
      <button
        className="back-button"
        type="button"
        onClick={onBack}
      >
        Back to Case
      </button>

      <div className="workspace-header">
        <div>
          <div className="section-label">
            CONTROLLED EXECUTION WORKSPACE
          </div>

          <h2>
            Actions
          </h2>

          <p>
            Inspect and safely simulate approved
            actions for
            {" "}
            {caseRecord.case_number}.
          </p>
        </div>

        <div className="case-count">
          {executableCount}

          <span>
            Executable
          </span>
        </div>
      </div>

      <div
        className="pipeline-status complete"
        style={{
          marginBottom: "18px",
        }}
      >
        Safety mode: Dry Run only. Live execution
        is not exposed by this interface.
      </div>

      {error && (
        <div className="error-panel">
          {error}
        </div>
      )}

      {statusMessage && (
        <div
          className={
            executing
              ? "pipeline-status running"
              : "pipeline-status complete"
          }
        >
          {statusMessage}
        </div>
      )}

      {loading && (
        <div className="empty-state">
          Loading action requests...
        </div>
      )}

      {!loading &&
        actions.length === 0 && (
          <div className="empty-state">
            No action requests exist for this
            case yet.
          </div>
        )}

      {!loading &&
        actions.length > 0 && (
          <div className="evidence-layout">
            <aside className="documents-panel">
              <div className="section-label">
                ACTION REQUESTS
              </div>

              <div className="document-list">
                {actions.map(
                  (action) => (
                    <button
                      key={
                        action.action_request_id
                      }
                      type="button"
                      className={
                        selectedAction
                          ?.action_request_id ===
                        action.action_request_id
                          ? "document-item active"
                          : "document-item"
                      }
                      onClick={() =>
                        selectAction(action)
                      }
                    >
                      <strong>
                        {action.action_type}
                      </strong>

                      <span>
                        {action.status}
                        {" | "}
                        {
                          action.policy
                            .risk_level
                        }
                      </span>
                    </button>
                  ),
                )}
              </div>
            </aside>

            <div className="document-detail-panel">
              {selectedAction && (
                <>
                  <div className="document-detail-header">
                    <div>
                      <div className="section-label">
                        SELECTED ACTION
                      </div>

                      <h3>
                        {
                          selectedAction.action_type
                        }
                      </h3>
                    </div>

                    <span
                      className={
                        `status-badge status-${selectedAction.status}`
                      }
                    >
                      {
                        selectedAction.status
                      }
                    </span>
                  </div>

                  <div className="document-metadata">
                    <div>
                      <span>
                        Action Request ID
                      </span>

                      <strong>
                        {
                          selectedAction
                            .action_request_id
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Policy
                      </span>

                      <strong>
                        {
                          selectedAction
                            .policy
                            .decision
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Risk Level
                      </span>

                      <strong>
                        {
                          selectedAction
                            .policy
                            .risk_level
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Approval Decision
                      </span>

                      <strong>
                        {
                          selectedAction
                            .approval_decision ??
                          "N/A"
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Reviewer
                      </span>

                      <strong>
                        {
                          selectedAction
                            .reviewer_ref ??
                          "N/A"
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Execution Enabled
                      </span>

                      <strong>
                        {
                          selectedAction
                            .execution_enabled
                            ? "Yes"
                            : "No"
                        }
                      </strong>
                    </div>
                  </div>

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        POLICY
                      </div>

                      <h3>
                        Guardrail Evaluation
                      </h3>
                    </div>
                  </div>

                  <article className="chunk-card">
                    <pre>
                      {
                        selectedAction
                          .policy
                          .rationale ||
                        "No policy rationale available."
                      }
                    </pre>
                  </article>

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        REVIEWED PAYLOAD
                      </div>

                      <h3>
                        Execution Payload
                      </h3>
                    </div>
                  </div>

                  <article className="chunk-card">
                    <pre>
                      {formatJson(
                        Object.keys(
                          selectedAction
                            .reviewed_payload,
                        ).length > 0
                          ? selectedAction
                              .reviewed_payload
                          : selectedAction
                              .payload,
                      )}
                    </pre>
                  </article>

                  <section className="evidence-upload-panel">
                    <div>
                      <div className="section-label">
                        SAFE EXECUTION
                      </div>

                      <h3>
                        Dry Run Simulation
                      </h3>

                      <p>
                        Simulate the approved action
                        without performing a live
                        external operation.
                      </p>
                    </div>

                    <div className="upload-controls">
                      <input
                        type="text"
                        value={requestedBy}
                        disabled={executing}
                        onChange={
                          (event) =>
                            setRequestedBy(
                              event.target.value,
                            )
                        }
                        placeholder="Requested by"
                        style={{
                          width: "100%",
                          boxSizing:
                            "border-box",
                          minHeight:
                            "44px",
                          padding:
                            "0 14px",
                          border:
                            "1px solid #405477",
                          borderRadius:
                            "10px",
                          background:
                            "#0b1423",
                          color:
                            "#dbe4f2",
                          fontSize:
                            "12px",
                          outline:
                            "none",
                        }}
                      />

                      <input
                        type="text"
                        value={idempotencyKey}
                        disabled={executing}
                        onChange={
                          (event) =>
                            setIdempotencyKey(
                              event.target.value,
                            )
                        }
                        placeholder="Idempotency key"
                        style={{
                          width: "100%",
                          boxSizing:
                            "border-box",
                          minHeight:
                            "44px",
                          padding:
                            "0 14px",
                          border:
                            "1px solid #405477",
                          borderRadius:
                            "10px",
                          background:
                            "#0b1423",
                          color:
                            "#dbe4f2",
                          fontSize:
                            "12px",
                          outline:
                            "none",
                        }}
                      />

                      <button
                        className="primary-action-button"
                        type="button"
                        disabled={
                          executing ||
                          !canDryRun(
                            selectedAction,
                          ) ||
                          requestedBy
                            .trim()
                            .length < 2 ||
                          idempotencyKey
                            .trim()
                            .length < 8
                        }
                        onClick={() =>
                          void handleDryRun()
                        }
                      >
                        {executing
                          ? "Simulating..."
                          : "Run Dry Simulation"}
                      </button>

                      {!canDryRun(
                        selectedAction,
                      ) && (
                        <div className="empty-state">
                          This action cannot be
                          simulated until it has
                          been approved.
                        </div>
                      )}
                    </div>
                  </section>

                  {executionResult && (
                    <>
                      <div className="chunks-header">
                        <div>
                          <div className="section-label">
                            EXECUTION RESULT
                          </div>

                          <h3>
                            Dry Run Outcome
                          </h3>
                        </div>
                      </div>

                      <div className="document-metadata">
                        <div>
                          <span>
                            Mode
                          </span>

                          <strong>
                            {
                              executionResult.mode
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            Status
                          </span>

                          <strong>
                            {
                              executionResult.status
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            Idempotent Replay
                          </span>

                          <strong>
                            {
                              executionResult
                                .idempotent_replay
                                ? "Yes"
                                : "No"
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            External Side Effect
                          </span>

                          <strong>
                            {
                              executionResult
                                .external_side_effect
                                ? "Yes"
                                : "No"
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            External Reference
                          </span>

                          <strong>
                            {
                              executionResult
                                .external_ref
                            }
                          </strong>
                        </div>
                      </div>

                      <article className="chunk-card">
                        <pre>
                          {formatJson(
                            executionResult
                              .details,
                          )}
                        </pre>
                      </article>
                    </>
                  )}

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        AUDIT
                      </div>

                      <h3>
                        Execution Timeline
                      </h3>
                    </div>
                  </div>

                  {loadingAudit && (
                    <div className="empty-state">
                      Loading audit events...
                    </div>
                  )}

                  {!loadingAudit &&
                    auditEvents.length ===
                      0 && (
                      <div className="empty-state">
                        No audit events available.
                      </div>
                    )}

                  {!loadingAudit &&
                    auditEvents.map(
                      (event) => (
                        <article
                          className="chunk-card"
                          key={event.id}
                        >
                          <div className="chunk-card-header">
                            <strong>
                              {
                                event.event_type
                              }
                            </strong>

                            <span>
                              {formatDate(
                                event.created_at,
                              )}
                            </span>
                          </div>

                          <div
                            style={{
                              padding:
                                "14px",
                              borderBottom:
                                "1px solid #22314a",
                            }}
                          >
                            <strong>
                              Actor:
                              {" "}
                              {
                                event.actor_ref ??
                                event.actor_type
                              }
                            </strong>
                          </div>

                          <pre>
                            {formatJson(
                              event.details,
                            )}
                          </pre>
                        </article>
                      ),
                    )}
                </>
              )}
            </div>
          </div>
        )}
    </section>
  )
}


export default ActionsWorkspace
