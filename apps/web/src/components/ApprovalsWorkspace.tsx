import {
  useEffect,
  useState,
} from "react"

import {
  decideAction,
  getActionAuditEvents,
  getActions,
  type ActionRequestRecord,
  type AuditEventRecord,
  type CaseRecord,
} from "../lib/api"


interface ApprovalsWorkspaceProps {
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


function decisionLabel(
  value: string | null | undefined,
): string {
  if (value === "approve") {
    return "Approved"
  }

  if (value === "reject") {
    return "Rejected"
  }

  return humanize(
    value,
  )
}


function approvalNextStep(
  action: ActionRequestRecord,
): string {
  if (action.status === "awaiting_approval") {
    return "A human reviewer must approve or reject this request before controlled execution can continue."
  }

  if (
    action.status === "approved" ||
    action.status === "auto_approved"
  ) {
    return "The request is approved and can move to the controlled execution workspace."
  }

  if (action.status === "rejected") {
    return "The request is stopped. No controlled action should execute from this approval."
  }

  if (action.status === "executed") {
    return "The approved request has already completed its controlled execution path."
  }

  return "Review the current request state and audit history before taking the next step."
}


function ApprovalsWorkspace({
  caseRecord,
  onBack,
}: ApprovalsWorkspaceProps) {
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
    loading,
    setLoading,
  ] = useState(true)

  const [
    loadingAudit,
    setLoadingAudit,
  ] = useState(false)

  const [
    deciding,
    setDeciding,
  ] = useState(false)

  const [
    reviewerRef,
    setReviewerRef,
  ] = useState(
    "frontend-reviewer",
  )

  const [
    comment,
    setComment,
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

        const pending =
          data.find(
            (action) =>
              action.status ===
              "awaiting_approval",
          )

        setAuditEvents([])

        setSelectedAction(
          pending ??
            data[0] ??
            null,
        )

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
            : "Unable to load governed actions.",
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

        const data =
          await getActionAuditEvents(
            caseRecord.id,
            actionRequestId,
            controller.signal,
          )

        setAuditEvents(data)
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


  async function handleDecision(
    decision: "approve" | "reject",
  ) {
    if (!selectedAction) {
      return
    }

    if (
      selectedAction.status !==
      "awaiting_approval"
    ) {
      setError(
        "This action is not awaiting human approval.",
      )

      return
    }

    const cleanReviewer =
      reviewerRef.trim()

    if (cleanReviewer.length < 2) {
      setError(
        "Reviewer reference must contain at least two characters.",
      )

      return
    }

    const actionRequestId =
      selectedAction.action_request_id

    try {
      setDeciding(true)
      setError(null)
      setStatusMessage(
        decision === "approve"
          ? "Submitting approval decision..."
          : "Submitting rejection decision...",
      )

      const updated =
        await decideAction(
          caseRecord.id,
          actionRequestId,
          decision,
          cleanReviewer,
          comment.trim() || null,
        )

      setSelectedAction(
        updated,
      )

      setActions(
        (current) =>
          current.map(
            (action) =>
              action.action_request_id ===
              updated.action_request_id
                ? updated
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

      setStatusMessage(
        decision === "approve"
          ? "Action approved successfully."
          : "Action rejected successfully.",
      )
    } catch (decisionError) {
      setStatusMessage(
        null,
      )

      setError(
        decisionError instanceof Error
          ? decisionError.message
          : "Approval decision failed.",
      )
    } finally {
      setDeciding(false)
    }
  }


  const pendingCount =
    actions.filter(
      (action) =>
        action.status ===
        "awaiting_approval",
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
            GOVERNANCE WORKSPACE
          </div>

          <h2>
            Approvals
          </h2>

          <p>
            Understand why an action needs review,
            what risk is involved, and what happens
            after the human decision.
          </p>
        </div>

        <div className="case-count">
          {pendingCount}

          <span>
            Pending
          </span>
        </div>
      </div>

      {!loading &&
        actions.length > 0 && (
          <section className="workspace-story-metrics">
            <article>
              <span>TOTAL REQUESTS</span>
              <strong>{actions.length}</strong>
              <p>
                Governed action requests connected
                to this case.
              </p>
            </article>

            <article>
              <span>WAITING FOR HUMAN</span>
              <strong>{pendingCount}</strong>
              <p>
                Requests that cannot proceed without
                a reviewer decision.
              </p>
            </article>

            <article>
              <span>SAFETY MODEL</span>
              <strong>HITL</strong>
              <p>
                Sensitive actions remain policy
                guarded and human controlled.
              </p>
            </article>
          </section>
        )}

      {error && (
        <div className="error-panel">
          {error}
        </div>
      )}

      {statusMessage && (
        <div
          className={
            deciding
              ? "pipeline-status running"
              : "pipeline-status complete"
          }
        >
          {statusMessage}
        </div>
      )}

      {loading && (
        <div className="empty-state">
          Loading governed actions...
        </div>
      )}

      {!loading &&
        actions.length === 0 && (
          <div className="empty-state">
            No governed action requests exist
            for this case yet.
          </div>
        )}

      {!loading &&
        actions.length > 0 && (
          <div className="evidence-layout">
            <aside className="documents-panel">
              <div className="section-label">
                APPROVAL QUEUE
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
                      onClick={() => {
                        setAuditEvents([])

                        setSelectedAction(
                          action,
                        )

                        setStatusMessage(
                          null,
                        )

                        setError(
                          null,
                        )
                      }}
                    >
                      <strong>
                        Request
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
                        APPROVAL STORY
                      </div>

                      <h3>
                        {humanize(
                          selectedAction.action_type,
                        )}
                      </h3>

                      <p>
                        Why this request exists, why
                        policy cares, and what the
                        reviewer controls.
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
                      <span>Human Review</span>
                      <strong>
                        {selectedAction
                          .policy
                          .requires_human_approval
                          ? "Required"
                          : "Not required"}
                      </strong>
                    </div>

                    <div>
                      <span>Execution</span>
                      <strong>
                        {selectedAction
                          .execution_enabled
                          ? "Enabled"
                          : "Guarded"}
                      </strong>
                    </div>
                  </div>

                  <div className="story-grid">
                    <article className="story-card">
                      <div className="story-step">
                        01
                      </div>

                      <div className="section-label">
                        PROPOSED ACTION
                      </div>

                      <h4>
                        What is CaseMesh asking to do?
                      </h4>

                      <p className="story-copy">
                        {humanize(
                          selectedAction.action_type,
                        )}
                        {" "}
                        has been proposed for
                        {" "}
                        {caseRecord.case_number}.
                        {" "}
                        The request was created
                        {" "}
                        {formatDate(
                          selectedAction.created_at,
                        )}.
                      </p>
                    </article>

                    <article className="story-card">
                      <div className="story-step">
                        02
                      </div>

                      <div className="section-label">
                        POLICY REASON
                      </div>

                      <h4>
                        Why is this governed?
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
                        HUMAN CONTROL
                      </div>

                      <h4>
                        What decision is needed?
                      </h4>

                      <p className="story-copy">
                        {selectedAction.status ===
                        "awaiting_approval"
                          ? "A reviewer must explicitly approve or reject this action before it can continue."
                          : selectedAction.approval_decision
                            ? `Human decision recorded: ${decisionLabel(
                                selectedAction.approval_decision,
                              )}.`
                            : "No active human decision is required in the current state."}
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
                        What happens now?
                      </h4>

                      <p className="story-copy">
                        {approvalNextStep(
                          selectedAction,
                        )}
                      </p>
                    </article>
                  </div>

                  {selectedAction.status ===
                    "awaiting_approval" && (
                    <section className="evidence-upload-panel">
                      <div>
                        <div className="section-label">
                          HUMAN-IN-THE-LOOP
                        </div>

                        <h3>
                          Record the human decision
                        </h3>

                        <p>
                          Confirm reviewer identity,
                          add an optional explanation,
                          then approve or reject.
                        </p>
                      </div>

                      <div className="upload-controls">
                        <input
                          type="text"
                          value={reviewerRef}
                          disabled={deciding}
                          onChange={
                            (event) =>
                              setReviewerRef(
                                event.target
                                  .value,
                              )
                          }
                          placeholder="Reviewer reference"
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

                        <textarea
                          value={comment}
                          disabled={deciding}
                          onChange={
                            (event) =>
                              setComment(
                                event.target
                                  .value,
                              )
                          }
                          rows={4}
                          placeholder="Reviewer comment (optional)"
                          style={{
                            width: "100%",
                            boxSizing:
                              "border-box",
                            resize:
                              "vertical",
                            padding:
                              "13px 14px",
                            border:
                              "1px solid #405477",
                            borderRadius:
                              "10px",
                            background:
                              "#0b1423",
                            color:
                              "#dbe4f2",
                            fontFamily:
                              "inherit",
                            fontSize:
                              "12px",
                            lineHeight:
                              1.6,
                            outline:
                              "none",
                          }}
                        />

                        <div className="approval-decision-buttons">
                          <button
                            className="primary-action-button"
                            type="button"
                            disabled={
                              deciding ||
                              reviewerRef
                                .trim()
                                .length < 2
                            }
                            onClick={() =>
                              void handleDecision(
                                "approve",
                              )
                            }
                          >
                            {deciding
                              ? "Processing..."
                              : "Approve"}
                          </button>

                          <button
                            className="secondary-action-button"
                            type="button"
                            disabled={
                              deciding ||
                              reviewerRef
                                .trim()
                                .length < 2
                            }
                            onClick={() =>
                              void handleDecision(
                                "reject",
                              )
                            }
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    </section>
                  )}

                  {selectedAction
                    .approval_decision && (
                    <section className="story-decision-banner">
                      <div>
                        <span>
                          HUMAN DECISION
                        </span>

                        <strong>
                          {decisionLabel(
                            selectedAction
                              .approval_decision,
                          )}
                        </strong>
                      </div>

                      <p>
                        Reviewer:
                        {" "}
                        {selectedAction
                          .reviewer_ref ??
                          "Unknown"}
                        {selectedAction
                          .approval_comment
                          ? ` · ${selectedAction.approval_comment}`
                          : ""}
                      </p>
                    </section>
                  )}

                  <details className="story-details">
                    <summary>
                      Proposed and reviewed payload
                    </summary>

                    <div className="story-details-body">
                      <article className="story-source-card">
                        <div>
                          <strong>
                            Proposed payload
                          </strong>
                        </div>

                        <pre className="story-raw-json">
                          {JSON.stringify(
                            selectedAction.payload,
                            null,
                            2,
                          )}
                        </pre>
                      </article>

                      {Object.keys(
                        selectedAction
                          .reviewed_payload,
                      ).length > 0 && (
                        <article className="story-source-card">
                          <div>
                            <strong>
                              Human reviewed payload
                            </strong>
                          </div>

                          <pre className="story-raw-json">
                            {JSON.stringify(
                              selectedAction
                                .reviewed_payload,
                              null,
                              2,
                            )}
                          </pre>
                        </article>
                      )}
                    </div>
                  </details>

                  <details className="story-details">
                    <summary>
                      Governance timeline
                    </summary>

                    <div className="story-details-body">
                      {loadingAudit && (
                        <div className="empty-state">
                          Loading audit events...
                        </div>
                      )}

                      {!loadingAudit &&
                        auditEvents.length === 0 && (
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
                      Developer view: request JSON
                    </summary>

                    <pre className="story-raw-json">
                      {JSON.stringify(
                        selectedAction,
                        null,
                        2,
                      )}
                    </pre>
                  </details>

                  {selectedAction
                    .error_message && (
                    <div className="error-panel">
                      {
                        selectedAction
                          .error_message
                      }
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
    </section>
  )
}


export default ApprovalsWorkspace
