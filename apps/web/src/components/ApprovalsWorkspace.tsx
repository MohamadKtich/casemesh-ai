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


function formatJson(
  value: Record<string, unknown>,
): string {
  return JSON.stringify(
    value,
    null,
    2,
  )
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
      setAuditEvents([])
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
            Review policy-governed action
            requests for
            {" "}
            {caseRecord.case_number}.
          </p>
        </div>

        <div className="case-count">
          {pendingCount}

          <span>
            Pending
          </span>
        </div>
      </div>

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
                      onClick={() => {
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
                        SELECTED REQUEST
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
                        Policy Decision
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
                        Human Approval
                      </span>

                      <strong>
                        {
                          selectedAction
                            .policy
                            .requires_human_approval
                            ? "Required"
                            : "Not Required"
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Investigation
                      </span>

                      <strong>
                        {
                          selectedAction
                            .investigation_run_id ??
                          "N/A"
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Created
                      </span>

                      <strong>
                        {formatDate(
                          selectedAction
                            .created_at,
                        )}
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
                        PAYLOAD
                      </div>

                      <h3>
                        Proposed Action Payload
                      </h3>
                    </div>
                  </div>

                  <article className="chunk-card">
                    <pre>
                      {formatJson(
                        selectedAction
                          .payload,
                      )}
                    </pre>
                  </article>

                  {Object.keys(
                    selectedAction
                      .reviewed_payload,
                  ).length > 0 && (
                    <>
                      <div className="chunks-header">
                        <div>
                          <div className="section-label">
                            REVIEWED PAYLOAD
                          </div>

                          <h3>
                            Human Reviewed Payload
                          </h3>
                        </div>
                      </div>

                      <article className="chunk-card">
                        <pre>
                          {formatJson(
                            selectedAction
                              .reviewed_payload,
                          )}
                        </pre>
                      </article>
                    </>
                  )}

                  {selectedAction.status ===
                    "awaiting_approval" && (
                    <section className="evidence-upload-panel">
                      <div>
                        <div className="section-label">
                          HUMAN-IN-THE-LOOP
                        </div>

                        <h3>
                          Approval Decision
                        </h3>

                        <p>
                          Review the policy,
                          risk and proposed
                          payload before
                          recording a human
                          decision.
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

                        <div
                          style={{
                            display:
                              "grid",
                            gridTemplateColumns:
                              "1fr 1fr",
                            gap: "10px",
                          }}
                        >
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
                            style={{
                              borderColor:
                                "#7d3344",
                              color:
                                "#ff899c",
                            }}
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    </section>
                  )}

                  {selectedAction
                    .approval_decision && (
                    <>
                      <div className="chunks-header">
                        <div>
                          <div className="section-label">
                            DECISION
                          </div>

                          <h3>
                            Human Review
                          </h3>
                        </div>
                      </div>

                      <div className="document-metadata">
                        <div>
                          <span>
                            Decision
                          </span>

                          <strong>
                            {
                              selectedAction
                                .approval_decision
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

                      <article className="chunk-card">
                        <pre>
                          {
                            selectedAction
                              .approval_comment ||
                            "No reviewer comment."
                          }
                        </pre>
                      </article>
                    </>
                  )}

                  {selectedAction
                    .error_message && (
                    <div className="error-panel">
                      {
                        selectedAction
                          .error_message
                      }
                    </div>
                  )}

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        AUDIT
                      </div>

                      <h3>
                        Governance Timeline
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
                        No audit events
                        available.
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


export default ApprovalsWorkspace