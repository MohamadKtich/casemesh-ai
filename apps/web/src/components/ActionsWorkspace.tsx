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


function humanize(
  value: string | null | undefined,
): string {
  if (!value) {
    return "N/A"
  }

  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
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


function executionNextStep(
  action: ActionRequestRecord,
): string {
  if (canDryRun(action)) {
    return "The action is approved. Run a dry simulation to verify behavior without creating an external side effect."
  }

  if (action.status === "awaiting_approval") {
    return "This action is waiting for human approval before any execution simulation can proceed."
  }

  if (action.status === "rejected") {
    return "This action is stopped because the human decision rejected it."
  }

  if (action.status === "executed") {
    return "Execution has already completed. Review the outcome and audit trail."
  }

  if (action.status === "failed") {
    return "Execution failed. Review the error and audit trail before retrying."
  }

  return "Review the policy state and audit history before continuing."
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
            Follow the execution story from policy
            decision to safe simulation and audit.
          </p>
        </div>

        <div className="case-count">
          {executableCount}

          <span>
            Executable
          </span>
        </div>
      </div>

      {!loading &&
        actions.length > 0 && (
          <section className="workspace-story-metrics">
            <article>
              <span>TOTAL ACTIONS</span>
              <strong>{actions.length}</strong>
              <p>
                Controlled action requests connected
                to this case.
              </p>
            </article>

            <article>
              <span>READY TO SIMULATE</span>
              <strong>{executableCount}</strong>
              <p>
                Approved requests that can safely run
                in dry-run mode.
              </p>
            </article>

            <article>
              <span>EXECUTION MODE</span>
              <strong>Dry Run</strong>
              <p>
                The interface does not expose live
                external side effects.
              </p>
            </article>
          </section>
        )}

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
                ACTION QUEUE
              </div>

              <div className="document-list">
                {actions.map(
                  (action, index) => (
                    <button
                      key={
                        action.action_request_id
                      }
                      type="button"
                      className={
                        selectedAction
                          ?.action_request_id ===
                        action.action_request_id
                          ? "document-item governance-queue-item active"
                          : "document-item governance-queue-item"
                      }
                      onClick={() =>
                        selectAction(action)
                      }
                    >
                      <strong>
                        Action
                        {" "}
                        {String(
                          index + 1,
                        ).padStart(
                          2,
                          "0",
                        )}
                        {" · "}
                        {humanize(
                          action.action_type,
                        )}
                      </strong>

                      <span>
                        {humanize(
                          action.status,
                        )}
                        {" · "}
                        {humanize(
                          action.policy
                            .risk_level,
                        )}
                        {" risk"}
                      </span>

                      <time>
                        {formatDate(
                          action.created_at,
                        )}
                      </time>
                    </button>
                  ),
                )}
              </div>
            </aside>

            <div className="document-detail-panel">
              {selectedAction && (
                <div className="investigation-story">
                  <section className="story-hero">
                    <div>
                      <div className="section-label">
                        ACTION STORY
                      </div>

                      <h3>
                        {humanize(
                          selectedAction.action_type,
                        )}
                      </h3>

                      <p>
                        What is allowed, what has been
                        approved, and what can safely
                        execute next.
                      </p>
                    </div>

                    <span
                      className={
                        `status-badge status-${selectedAction.status}`
                      }
                    >
                      {humanize(
                        selectedAction.status,
                      )}
                    </span>
                  </section>

                  <div className="story-metrics">
                    <div>
                      <span>Policy</span>
                      <strong>
                        {humanize(
                          selectedAction
                            .policy
                            .decision,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Risk</span>
                      <strong>
                        {humanize(
                          selectedAction
                            .policy
                            .risk_level,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Approval</span>
                      <strong>
                        {humanize(
                          selectedAction
                            .approval_decision,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Safety</span>
                      <strong>
                        Dry Run
                      </strong>
                    </div>
                  </div>

                  <section className="story-timeline evidence-story-timeline">
                    <div className="story-timeline-item done">
                      <span>1</span>
                      <strong>Requested</strong>
                      <small>
                        Action request created
                      </small>
                    </div>

                    <div className="story-timeline-item done">
                      <span>2</span>
                      <strong>Policy</strong>
                      <small>
                        Risk and permission assessed
                      </small>
                    </div>

                    <div
                      className={
                        selectedAction
                          .approval_decision ||
                        selectedAction.status ===
                          "auto_approved"
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>3</span>
                      <strong>Approval</strong>
                      <small>
                        Human or policy decision
                      </small>
                    </div>

                    <div
                      className={
                        executionResult ||
                        selectedAction.status ===
                          "executed"
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>4</span>
                      <strong>Simulation</strong>
                      <small>
                        Safe execution outcome
                      </small>
                    </div>
                  </section>

                  <div className="story-grid">
                    <article className="story-card">
                      <div className="story-step">
                        01
                      </div>

                      <div className="section-label">
                        REQUEST
                      </div>

                      <h4>
                        What action is being attempted?
                      </h4>

                      <p className="story-copy">
                        {humanize(
                          selectedAction.action_type,
                        )}
                        {" "}
                        was requested for
                        {" "}
                        {caseRecord.case_number}.
                      </p>
                    </article>

                    <article className="story-card">
                      <div className="story-step">
                        02
                      </div>

                      <div className="section-label">
                        GUARDRAIL
                      </div>

                      <h4>
                        Why can or can’t it proceed?
                      </h4>

                      <p className="story-copy">
                        {selectedAction
                          .policy
                          .rationale ||
                          "No policy rationale is available."}
                      </p>
                    </article>

                    <article className="story-card story-card-accent">
                      <div className="story-step">
                        03
                      </div>

                      <div className="section-label">
                        APPROVAL STATE
                      </div>

                      <h4>
                        Has a human cleared it?
                      </h4>

                      <p className="story-copy">
                        {selectedAction
                          .approval_decision
                          ? `Decision: ${humanize(
                              selectedAction
                                .approval_decision,
                            )}. Reviewer: ${selectedAction.reviewer_ref ??
                              "N/A"}.`
                          : selectedAction.status ===
                              "auto_approved"
                            ? "Policy automatically approved this request."
                            : "No completed approval decision is recorded yet."}
                      </p>
                    </article>

                    <article className="story-card story-next-action">
                      <div className="story-step">
                        04
                      </div>

                      <div className="section-label">
                        NEXT STEP
                      </div>

                      <h4>
                        What should happen now?
                      </h4>

                      <p className="story-copy">
                        {executionNextStep(
                          selectedAction,
                        )}
                      </p>
                    </article>
                  </div>

                  <details className="story-details">
                    <summary>
                      Execution payload
                    </summary>

                    <pre className="story-raw-json">
                      {JSON.stringify(
                        Object.keys(
                          selectedAction
                            .reviewed_payload,
                        ).length > 0
                          ? selectedAction
                              .reviewed_payload
                          : selectedAction
                              .payload,
                        null,
                        2,
                      )}
                    </pre>
                  </details>

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
                    <section className="story-decision-banner">
                      <div>
                        <span>
                          DRY RUN OUTCOME
                        </span>

                        <strong>
                          {humanize(
                            executionResult.status,
                          )}
                        </strong>
                      </div>

                      <p>
                        Mode:
                        {" "}
                        {humanize(
                          executionResult.mode,
                        )}
                        {" · "}
                        External side effect:
                        {" "}
                        {executionResult
                          .external_side_effect
                          ? "Yes"
                          : "No"}
                        {" · "}
                        Reference:
                        {" "}
                        {executionResult.external_ref}
                      </p>
                    </section>
                  )}

                  <details className="story-details">
                    <summary>
                      Execution audit timeline
                    </summary>

                    <div className="story-details-body">
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
                              className="story-source-card"
                              key={event.id}
                            >
                              <div>
                                <strong>
                                  {humanize(
                                    event.event_type,
                                  )}
                                </strong>

                                <span>
                                  {formatDate(
                                    event.created_at,
                                  )}
                                </span>
                              </div>

                              <p>
                                Actor:
                                {" "}
                                {event.actor_ref ??
                                  event.actor_type}
                              </p>
                            </article>
                          ),
                        )}
                    </div>
                  </details>

                  <details className="story-details story-raw-details">
                    <summary>
                      Developer view: action JSON
                    </summary>

                    <pre className="story-raw-json">
                      {JSON.stringify(
                        selectedAction,
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          </div>
        )}
    </section>
  )
}


export default ActionsWorkspace
