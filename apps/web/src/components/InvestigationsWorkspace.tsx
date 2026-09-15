import {
  useEffect,
  useState,
  type FormEvent,
} from "react"

import {
  getInvestigations,
  startInvestigation,
  type CaseRecord,
  type InvestigationRun,
} from "../lib/api"


interface InvestigationsWorkspaceProps {
  caseRecord: CaseRecord
  onBack: () => void
}


function stateClass(
  state: InvestigationRun["state"],
): string {
  if (state === "completed") {
    return "status-ready"
  }

  if (state === "running") {
    return "status-processing"
  }

  if (state === "failed") {
    return "status-failed"
  }

  return "status-uploaded"
}


function formatDate(
  value: string | null,
): string {
  if (!value) {
    return "N/A"
  }

  return new Date(
    value,
  ).toLocaleString()
}


function formatReviewValue(
  value: string | null,
): string {
  if (!value) {
    return "N/A"
  }

  return value
    .split("_")
    .join(" ")
}


function formatReasonCodes(
  values: string[],
): string {
  if (values.length === 0) {
    return "None"
  }

  return values
    .map(
      (value) =>
        value
          .split("_")
          .join(" "),
    )
    .join(", ")
}


function InvestigationsWorkspace({
  caseRecord,
  onBack,
}: InvestigationsWorkspaceProps) {
  const [
    runs,
    setRuns,
  ] = useState<InvestigationRun[]>([])

  const [
    selectedRun,
    setSelectedRun,
  ] = useState<InvestigationRun | null>(
    null,
  )

  const [
    objective,
    setObjective,
  ] = useState(
    "Determine which database is used in the CaseMesh Azure environment and report only evidence-supported facts.",
  )

  const [
    loading,
    setLoading,
  ] = useState(true)

  const [
    starting,
    setStarting,
  ] = useState(false)

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

    async function loadRuns() {
      try {
        setLoading(true)

        const data =
          await getInvestigations(
            caseRecord.id,
            controller.signal,
          )

        setRuns(data)

        if (data.length > 0) {
          setSelectedRun(
            data[0],
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
            : "Unable to load investigations.",
        )
      } finally {
        setLoading(false)
      }
    }

    void loadRuns()

    return () => {
      controller.abort()
    }
  }, [caseRecord.id])


  async function handleStart(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    const cleanObjective =
      objective.trim()

    if (cleanObjective.length < 5) {
      setError(
        "Investigation objective must contain at least five characters.",
      )

      return
    }

    try {
      setStarting(true)
      setError(null)

      setStatusMessage(
        "Running LangGraph investigation. This may take a moment...",
      )

      const run =
        await startInvestigation(
          caseRecord.id,
          cleanObjective,
        )

      setSelectedRun(
        run,
      )

      const refreshed =
        await getInvestigations(
          caseRecord.id,
        )

      setRuns(
        refreshed,
      )

      setStatusMessage(
        run.state === "completed"
          ? "Investigation completed successfully."
          : `Investigation finished with state: ${run.state}.`,
      )
    } catch (startError) {
      setStatusMessage(
        null,
      )

      setError(
        startError instanceof Error
          ? startError.message
          : "Investigation workflow failed.",
      )

      try {
        const refreshed =
          await getInvestigations(
            caseRecord.id,
          )

        setRuns(
          refreshed,
        )

        if (refreshed.length > 0) {
          setSelectedRun(
            refreshed[0],
          )
        }
      } catch {
        // Keep the original workflow error.
      }
    } finally {
      setStarting(false)
    }
  }


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
            INVESTIGATIONS WORKSPACE
          </div>

          <h2>
            Investigations
          </h2>

          <p>
            Run evidence-grounded LangGraph
            investigations for
            {" "}
            {caseRecord.case_number}.
          </p>
        </div>

        <div className="case-count">
          {runs.length}

          <span>
            Runs
          </span>
        </div>
      </div>

      <section className="evidence-upload-panel">
        <div>
          <div className="section-label">
            AGENT WORKFLOW
          </div>

          <h3>
            Start investigation
          </h3>

          <p>
            CaseMesh will analyze the case,
            retrieve grounded evidence,
            assess evidence sufficiency,
            identify gaps and produce cited
            findings.
          </p>
        </div>

        <form
          className="upload-controls"
          onSubmit={
            (event) =>
              void handleStart(event)
          }
        >
          <textarea
            value={objective}
            disabled={starting}
            onChange={
              (event) =>
                setObjective(
                  event.target.value,
                )
            }
            rows={5}
            placeholder="Describe the investigation objective..."
            style={{
              width: "100%",
              boxSizing: "border-box",
              resize: "vertical",
              padding: "13px 14px",
              border: "1px solid #405477",
              borderRadius: "10px",
              background: "#0b1423",
              color: "#dbe4f2",
              fontFamily: "inherit",
              fontSize: "12px",
              lineHeight: 1.6,
              outline: "none",
            }}
          />

          <button
            className="primary-action-button"
            type="submit"
            disabled={
              starting ||
              objective.trim().length < 5
            }
          >
            {starting
              ? "Investigating..."
              : "Start Investigation"}
          </button>
        </form>

        {statusMessage && (
          <div
            className={
              starting
                ? "pipeline-status running"
                : "pipeline-status complete"
            }
          >
            {statusMessage}
          </div>
        )}
      </section>

      {error && (
        <div className="error-panel">
          {error}
        </div>
      )}

      {loading && (
        <div className="empty-state">
          Loading investigations...
        </div>
      )}

      {!loading &&
        runs.length === 0 && (
          <div className="empty-state">
            No investigations have been run
            for this case yet.
          </div>
        )}

      {!loading &&
        runs.length > 0 && (
          <div className="evidence-layout">
            <aside className="documents-panel">
              <div className="section-label">
                INVESTIGATION RUNS
              </div>

              <div className="document-list">
                {runs.map(
                  (run) => (
                    <button
                      key={run.workflow_id}
                      type="button"
                      className={
                        selectedRun?.workflow_id ===
                        run.workflow_id
                          ? "document-item active"
                          : "document-item"
                      }
                      onClick={() =>
                        setSelectedRun(
                          run,
                        )
                      }
                    >
                      <strong>
                        {run.objective ??
                          "Investigation"}
                      </strong>

                      <span>
                        {run.state}
                        {" | "}
                        {run.confidence ??
                          "no confidence"}
                      </span>
                    </button>
                  ),
                )}
              </div>
            </aside>

            <div className="document-detail-panel">
              {selectedRun && (
                <>
                  <div className="document-detail-header">
                    <div>
                      <div className="section-label">
                        SELECTED RUN
                      </div>

                      <h3>
                        Investigation Result
                      </h3>
                    </div>

                    <span
                      className={
                        `status-badge ${stateClass(
                          selectedRun.state,
                        )}`
                      }
                    >
                      {selectedRun.state}
                    </span>
                  </div>

                  <div className="document-metadata">
                    <div>
                      <span>
                        Workflow ID
                      </span>

                      <strong>
                        {
                          selectedRun.workflow_id
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Confidence
                      </span>

                      <strong>
                        {
                          selectedRun.confidence ??
                          "N/A"
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Abstained
                      </span>

                      <strong>
                        {selectedRun.abstained
                          ? "Yes"
                          : "No"}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Current Step
                      </span>

                      <strong>
                        {
                          selectedRun.current_step ??
                          "N/A"
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Attempt
                      </span>

                      <strong>
                        {selectedRun.attempt}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Completed
                      </span>

                      <strong>
                        {formatDate(
                          selectedRun.completed_at,
                        )}
                      </strong>
                    </div>
                  </div>

                  {selectedRun.risk_triggers && (
                    <>
                      <div className="chunks-header">
                        <div>
                          <div className="section-label">
                            RISK REVIEW SIGNALS
                          </div>

                          <h3>
                            Risk Review Signals
                          </h3>
                        </div>
                      </div>

                      <div className="document-metadata">
                        <div>
                          <span>
                            Second Review Requested
                          </span>

                          <strong>
                            {
                              selectedRun
                                .risk_triggers
                                .second_review_requested
                                ? "Yes"
                                : "No"
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            Reason Codes
                          </span>

                          <strong>
                            {formatReasonCodes(
                              selectedRun
                                .risk_triggers
                                .reason_codes,
                            )}
                          </strong>
                        </div>
                      </div>
                    </>
                  )}

                  {selectedRun.second_review && (
                    <>
                      <div className="chunks-header">
                        <div>
                          <div className="section-label">
                            INDEPENDENT SECOND REVIEW
                          </div>

                          <h3>
                            Independent Second Review
                          </h3>
                        </div>
                      </div>

                      <div className="document-metadata">
                        <div>
                          <span>
                            Status
                          </span>

                          <strong>
                            {formatReviewValue(
                              selectedRun
                                .second_review
                                .status,
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>
                            Agreement
                          </span>

                          <strong>
                            {formatReviewValue(
                              selectedRun
                                .second_review
                                .agreement,
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>
                            Risk Level
                          </span>

                          <strong>
                            {formatReviewValue(
                              selectedRun
                                .second_review
                                .risk_level,
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>
                            Effective Route
                          </span>

                          <strong>
                            {formatReviewValue(
                              selectedRun
                                .second_review
                                .effective_route,
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>
                            Forced Human Review
                          </span>

                          <strong>
                            {
                              selectedRun
                                .second_review
                                .forced_human_review
                                ? "Yes"
                                : "No"
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            Guardrail Decision
                          </span>

                          <strong>
                            {formatReviewValue(
                              selectedRun
                                .second_review
                                .guardrail_decision,
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>
                            Reason Codes
                          </span>

                          <strong>
                            {formatReasonCodes(
                              selectedRun
                                .second_review
                                .reason_codes,
                            )}
                          </strong>
                        </div>
                      </div>
                    </>
                  )}

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        OBJECTIVE
                      </div>

                      <h3>
                        Investigation Objective
                      </h3>
                    </div>
                  </div>

                  <article className="chunk-card">
                    <pre>
                      {selectedRun.objective ??
                        "No objective available."}
                    </pre>
                  </article>

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        CASE ANALYSIS
                      </div>

                      <h3>
                        Analysis
                      </h3>
                    </div>
                  </div>

                  <article className="chunk-card">
                    <pre>
                      {selectedRun.analysis ??
                        "No analysis available."}
                    </pre>
                  </article>

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        ASSESSMENT
                      </div>

                      <h3>
                        Evidence Assessment
                      </h3>
                    </div>
                  </div>

                  <article className="chunk-card">
                    <pre>
                      {selectedRun.assessment ??
                        "No assessment available."}
                    </pre>
                  </article>

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        FINDINGS
                      </div>

                      <h3>
                        Grounded Findings
                      </h3>
                    </div>
                  </div>

                  <article className="chunk-card">
                    <pre>
                      {selectedRun.findings ??
                        "No findings available."}
                    </pre>
                  </article>

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        PLAN
                      </div>

                      <h3>
                        Investigation Plan
                      </h3>
                    </div>
                  </div>

                  {selectedRun.plan.length ===
                    0 && (
                    <div className="empty-state">
                      No plan steps available.
                    </div>
                  )}

                  {selectedRun.plan.map(
                    (item) => (
                      <article
                        className="chunk-card"
                        key={item.step}
                      >
                        <div className="chunk-card-header">
                          <strong>
                            Step {item.step}
                          </strong>
                        </div>

                        <pre>
                          {item.title}
                        </pre>
                      </article>
                    ),
                  )}

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        EVIDENCE
                      </div>

                      <h3>
                        Retrieved Evidence
                      </h3>
                    </div>
                  </div>

                  {selectedRun.evidence.length ===
                    0 && (
                    <div className="empty-state">
                      No evidence references
                      available.
                    </div>
                  )}

                  {selectedRun.evidence.map(
                    (item, index) => (
                      <article
                        className="chunk-card"
                        key={item.chunk_id}
                      >
                        <div className="chunk-card-header">
                          <strong>
                            Evidence #{index + 1}
                          </strong>

                          <span>
                            Chunk #{item.chunk_index}
                            {" | "}
                            Hybrid:
                            {" "}
                            {item.hybrid_score.toFixed(
                              6,
                            )}
                          </span>
                        </div>

                        <pre>
                          {item.excerpt}
                        </pre>
                      </article>
                    ),
                  )}

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        CITATIONS
                      </div>

                      <h3>
                        Grounding Citations
                      </h3>
                    </div>
                  </div>

                  {selectedRun.citations.length ===
                    0 && (
                    <div className="empty-state">
                      No citations available.
                    </div>
                  )}

                  {selectedRun.citations.map(
                    (citation) => (
                      <article
                        className="chunk-card"
                        key={
                          `${citation.label}-${citation.chunk_id}`
                        }
                      >
                        <div className="chunk-card-header">
                          <strong>
                            [{citation.label}]
                          </strong>

                          <span>
                            Chunk #
                            {
                              citation.chunk_index
                            }
                          </span>
                        </div>

                        <pre>
                          {citation.excerpt}
                        </pre>
                      </article>
                    ),
                  )}

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        EVIDENCE GAPS
                      </div>

                      <h3>
                        Identified Gaps
                      </h3>
                    </div>
                  </div>

                  {selectedRun.gaps.length ===
                    0 ? (
                    <div className="pipeline-status complete">
                      No material evidence gaps
                      identified.
                    </div>
                  ) : (
                    selectedRun.gaps.map(
                      (gap) => (
                        <article
                          className="chunk-card"
                          key={gap.code}
                        >
                          <div className="chunk-card-header">
                            <strong>
                              {gap.code}
                            </strong>
                          </div>

                          <pre>
                            {gap.description}
                          </pre>
                        </article>
                      ),
                    )
                  )}

                  {selectedRun.error_message && (
                    <div className="error-panel">
                      {
                        selectedRun.error_message
                      }
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
    </section>
  )
}


export default InvestigationsWorkspace