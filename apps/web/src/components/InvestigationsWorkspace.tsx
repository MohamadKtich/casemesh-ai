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


function formatRunDate(
  value: string | null,
): string {
  if (!value) {
    return "Date unavailable"
  }

  return new Intl.DateTimeFormat(
    "en",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    },
  ).format(
    new Date(value),
  )
}


function objectivePreview(
  value: string | null,
): string {
  if (!value) {
    return "No objective recorded."
  }

  const clean =
    value.replace(/\s+/g, " ").trim()

  if (clean.length <= 92) {
    return clean
  }

  return `${clean.slice(0, 89)}...`
}


function formatLabel(
  value: string | null | undefined,
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


function deriveNextStep(
  run: InvestigationRun,
): string {
  if (run.state === "failed") {
    return "Review the workflow error, correct the underlying issue, and run the investigation again."
  }

  if (
    run.second_review?.forced_human_review ||
    run.second_review?.effective_route === "human_review"
  ) {
    return "Human review is required before any sensitive action can move forward."
  }

  if (run.abstained) {
    return "Collect stronger evidence before making a decision. The investigation abstained from a confident conclusion."
  }

  if (run.gaps.length > 0) {
    return "Resolve the identified evidence gaps, then reassess the case before taking action."
  }

  if (run.state === "completed") {
    return "Review the grounded findings and citations, then continue to approval or controlled action only if policy allows."
  }

  return "The investigation is still in progress. Wait for the current workflow step to finish."
}


function deriveRiskSummary(
  run: InvestigationRun,
): string {
  const riskLevel =
    run.second_review?.risk_level

  if (riskLevel) {
    return `${formatLabel(riskLevel)} risk`
  }

  if (
    run.risk_triggers
      ?.second_review_requested
  ) {
    return "Second review requested"
  }

  return "No elevated review signal"
}


function toneClass(
  value: string | null | undefined,
): string {
  if (
    value === "critical" ||
    value === "high" ||
    value === "failed" ||
    value === "blocked"
  ) {
    return "story-tone-danger"
  }

  if (
    value === "medium" ||
    value === "uncertain" ||
    value === "human_review"
  ) {
    return "story-tone-warning"
  }

  if (
    value === "low" ||
    value === "agree" ||
    value === "continue" ||
    value === "completed"
  ) {
    return "story-tone-good"
  }

  return "story-tone-neutral"
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
            Follow each investigation as a
            readable evidence story for
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
            CaseMesh analyzes the case,
            retrieves grounded evidence,
            assesses sufficiency, identifies
            gaps, and produces cited findings.
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

              <div className="document-list investigation-run-list">
                {runs.map(
                  (run, index) => (
                    <button
                      key={run.workflow_id}
                      type="button"
                      className={
                        selectedRun?.workflow_id ===
                        run.workflow_id
                          ? "document-item investigation-run-item active"
                          : "document-item investigation-run-item"
                      }
                      onClick={() =>
                        setSelectedRun(
                          run,
                        )
                      }
                    >
                      <div className="investigation-run-heading">
                        <strong>
                          Run {String(
                            index + 1,
                          ).padStart(
                            2,
                            "0",
                          )}
                        </strong>

                        <span
                          className={
                            `investigation-run-state ${stateClass(
                              run.state,
                            )}`
                          }
                        >
                          {formatLabel(
                            run.state,
                          )}
                        </span>
                      </div>

                      <p className="investigation-run-objective">
                        {objectivePreview(
                          run.objective,
                        )}
                      </p>

                      <div className="investigation-run-stats">
                        <span>
                          {formatLabel(
                            run.confidence,
                          )}
                          {" "}
                          confidence
                        </span>

                        <span>
                          {run.evidence.length}
                          {" "}
                          evidence
                        </span>

                        <span>
                          {run.citations.length}
                          {" "}
                          citations
                        </span>
                      </div>

                      <time>
                        {formatRunDate(
                          run.completed_at ??
                            run.created_at,
                        )}
                      </time>
                    </button>
                  ),
                )}
              </div>
            </aside>

            <div className="document-detail-panel">
              {selectedRun && (
                <div className="investigation-story">
                  <section className="story-hero">
                    <div>
                      <div className="section-label">
                        INVESTIGATION STORY
                      </div>

                      <h3>
                        From objective to decision
                      </h3>

                      <p>
                        {caseRecord.title}
                      </p>
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
                  </section>

                  <div className="story-metrics">
                    <div>
                      <span>Confidence</span>
                      <strong>
                        {formatLabel(
                          selectedRun.confidence,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Evidence</span>
                      <strong>
                        {selectedRun.evidence.length}
                      </strong>
                    </div>

                    <div>
                      <span>Citations</span>
                      <strong>
                        {selectedRun.citations.length}
                      </strong>
                    </div>

                    <div>
                      <span>Evidence Gaps</span>
                      <strong>
                        {selectedRun.gaps.length}
                      </strong>
                    </div>
                  </div>

                  <section className="story-timeline">
                    <div
                      className={
                        selectedRun.objective
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>1</span>
                      <strong>Objective</strong>
                      <small>
                        Investigation question defined
                      </small>
                    </div>

                    <div
                      className={
                        selectedRun.plan.length > 0
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>2</span>
                      <strong>Plan</strong>
                      <small>
                        Workflow steps prepared
                      </small>
                    </div>

                    <div
                      className={
                        selectedRun.evidence.length > 0
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>3</span>
                      <strong>Evidence</strong>
                      <small>
                        Relevant sources retrieved
                      </small>
                    </div>

                    <div
                      className={
                        selectedRun.analysis ||
                        selectedRun.findings
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>4</span>
                      <strong>Analysis</strong>
                      <small>
                        Evidence interpreted
                      </small>
                    </div>

                    <div
                      className={
                        selectedRun.risk_triggers ||
                        selectedRun.second_review ||
                        selectedRun.state === "completed"
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>5</span>
                      <strong>Review</strong>
                      <small>
                        {selectedRun.second_review ||
                        selectedRun.risk_triggers
                          ?.second_review_requested
                          ? "Risk and routing assessed"
                          : selectedRun.state === "completed"
                            ? "No elevated review required"
                            : "Risk and routing pending"}
                      </small>
                    </div>

                    <div
                      className={
                        selectedRun.state === "completed"
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>6</span>
                      <strong>Outcome</strong>
                      <small>
                        Next step made explicit
                      </small>
                    </div>
                  </section>

                  <div className="story-grid">
                    <article className="story-card">
                      <div className="story-step">
                        01
                      </div>

                      <div className="section-label">
                        THE QUESTION
                      </div>

                      <h4>
                        What are we trying to determine?
                      </h4>

                      <p className="story-copy">
                        {selectedRun.objective ??
                          "No objective available."}
                      </p>
                    </article>

                    <article className="story-card story-card-accent">
                      <div className="story-step">
                        02
                      </div>

                      <div className="section-label">
                        WHAT CASEMESH FOUND
                      </div>

                      <h4>
                        Grounded finding
                      </h4>

                      <p className="story-copy">
                        {selectedRun.findings ??
                          selectedRun.assessment ??
                          "No grounded finding is available yet."}
                      </p>
                    </article>

                    <article className="story-card">
                      <div className="story-step">
                        03
                      </div>

                      <div className="section-label">
                        WHY THIS RESULT
                      </div>

                      <h4>
                        Evidence picture
                      </h4>

                      <p className="story-copy">
                        CaseMesh retrieved
                        {" "}
                        {selectedRun.evidence.length}
                        {" "}
                        evidence reference
                        {selectedRun.evidence.length === 1
                          ? ""
                          : "s"}
                        {" "}
                        and attached
                        {" "}
                        {selectedRun.citations.length}
                        {" "}
                        citation
                        {selectedRun.citations.length === 1
                          ? ""
                          : "s"}
                        {" "}
                        to keep the result traceable.
                      </p>

                      {selectedRun.evidence
                        .slice(0, 3)
                        .map(
                          (item, index) => (
                            <div
                              className="story-evidence-preview"
                              key={item.chunk_id}
                            >
                              <strong>
                                Evidence {index + 1}
                              </strong>

                              <span>
                                Chunk #{item.chunk_index}
                                {" | "}
                                Hybrid score
                                {" "}
                                {item.hybrid_score.toFixed(
                                  4,
                                )}
                              </span>

                              <p>
                                {item.excerpt}
                              </p>
                            </div>
                          ),
                        )}
                    </article>

                    <article className="story-card">
                      <div className="story-step">
                        04
                      </div>

                      <div className="section-label">
                        ANALYSIS
                      </div>

                      <h4>
                        How the evidence was interpreted
                      </h4>

                      <p className="story-copy">
                        {selectedRun.analysis ??
                          "No analysis is available yet."}
                      </p>

                      {selectedRun.assessment && (
                        <div className="story-callout">
                          <span>
                            Evidence assessment
                          </span>

                          <p>
                            {selectedRun.assessment}
                          </p>
                        </div>
                      )}
                    </article>

                    <article className="story-card">
                      <div className="story-step">
                        05
                      </div>

                      <div className="section-label">
                        RISK & REVIEW
                      </div>

                      <h4>
                        What needs extra attention?
                      </h4>

                      <div className="story-status-row">
                        <span
                          className={
                            `story-pill ${toneClass(
                              selectedRun
                                .second_review
                                ?.risk_level,
                            )}`
                          }
                        >
                          {deriveRiskSummary(
                            selectedRun,
                          )}
                        </span>

                        {selectedRun.second_review && (
                          <span
                            className={
                              `story-pill ${toneClass(
                                selectedRun
                                  .second_review
                                  .effective_route,
                              )}`
                            }
                          >
                            Route:
                            {" "}
                            {formatLabel(
                              selectedRun
                                .second_review
                                .effective_route,
                            )}
                          </span>
                        )}
                      </div>

                      {selectedRun.risk_triggers && (
                        <p className="story-copy">
                          Review reasons:
                          {" "}
                          {formatReasonCodes(
                            selectedRun
                              .risk_triggers
                              .reason_codes,
                          )}
                        </p>
                      )}

                      {selectedRun.second_review && (
                        <div className="story-review-grid">
                          <div>
                            <span>Status</span>
                            <strong>
                              {formatLabel(
                                selectedRun
                                  .second_review
                                  .status,
                              )}
                            </strong>
                          </div>

                          <div>
                            <span>Agreement</span>
                            <strong>
                              {formatLabel(
                                selectedRun
                                  .second_review
                                  .agreement,
                              )}
                            </strong>
                          </div>

                          <div>
                            <span>Guardrail</span>
                            <strong>
                              {formatLabel(
                                selectedRun
                                  .second_review
                                  .guardrail_decision,
                              )}
                            </strong>
                          </div>

                          <div>
                            <span>Human Review</span>
                            <strong>
                              {selectedRun
                                .second_review
                                .forced_human_review
                                ? "Required"
                                : "Not forced"}
                            </strong>
                          </div>
                        </div>
                      )}
                    </article>

                    <article className="story-card story-next-action">
                      <div className="story-step">
                        06
                      </div>

                      <div className="section-label">
                        NEXT ACTION
                      </div>

                      <h4>
                        What should happen now?
                      </h4>

                      <p className="story-copy">
                        {deriveNextStep(
                          selectedRun,
                        )}
                      </p>

                      <div className="story-next-meta">
                        <span>
                          Current step
                        </span>

                        <strong>
                          {formatLabel(
                            selectedRun.current_step,
                          )}
                        </strong>

                        <span>
                          Completed
                        </span>

                        <strong>
                          {formatDate(
                            selectedRun.completed_at,
                          )}
                        </strong>
                      </div>
                    </article>
                  </div>

                  <details className="story-details">
                    <summary>
                      Investigation plan
                    </summary>

                    <div className="story-details-body">
                      {selectedRun.plan.length ===
                        0 ? (
                        <div className="empty-state">
                          No plan steps available.
                        </div>
                      ) : (
                        selectedRun.plan.map(
                          (item) => (
                            <div
                              className="story-detail-row"
                              key={item.step}
                            >
                              <span>
                                Step {item.step}
                              </span>

                              <strong>
                                {item.title}
                              </strong>
                            </div>
                          ),
                        )
                      )}
                    </div>
                  </details>

                  <details className="story-details">
                    <summary>
                      All retrieved evidence
                    </summary>

                    <div className="story-details-body">
                      {selectedRun.evidence.length ===
                        0 ? (
                        <div className="empty-state">
                          No evidence references
                          available.
                        </div>
                      ) : (
                        selectedRun.evidence.map(
                          (item, index) => (
                            <article
                              className="story-source-card"
                              key={item.chunk_id}
                            >
                              <div>
                                <strong>
                                  Evidence #{index + 1}
                                </strong>

                                <span>
                                  Document
                                  {" "}
                                  {item.document_id}
                                  {" | "}
                                  Chunk
                                  {" "}
                                  {item.chunk_index}
                                </span>
                              </div>

                              <p>
                                {item.excerpt}
                              </p>
                            </article>
                          ),
                        )
                      )}
                    </div>
                  </details>

                  <details className="story-details">
                    <summary>
                      Grounding citations
                    </summary>

                    <div className="story-details-body">
                      {selectedRun.citations.length ===
                        0 ? (
                        <div className="empty-state">
                          No citations available.
                        </div>
                      ) : (
                        selectedRun.citations.map(
                          (citation) => (
                            <article
                              className="story-source-card"
                              key={
                                `${citation.label}-${citation.chunk_id}`
                              }
                            >
                              <div>
                                <strong>
                                  [{citation.label}]
                                </strong>

                                <span>
                                  Chunk
                                  {" "}
                                  {citation.chunk_index}
                                </span>
                              </div>

                              <p>
                                {citation.excerpt}
                              </p>
                            </article>
                          ),
                        )
                      )}
                    </div>
                  </details>

                  <details className="story-details">
                    <summary>
                      Evidence gaps
                    </summary>

                    <div className="story-details-body">
                      {selectedRun.gaps.length ===
                        0 ? (
                        <div className="pipeline-status complete">
                          No material evidence gaps
                          identified.
                        </div>
                      ) : (
                        selectedRun.gaps.map(
                          (gap) => (
                            <div
                              className="story-detail-row"
                              key={gap.code}
                            >
                              <span>
                                {gap.code}
                              </span>

                              <strong>
                                {gap.description}
                              </strong>
                            </div>
                          ),
                        )
                      )}
                    </div>
                  </details>

                  <details className="story-details story-raw-details">
                    <summary>
                      Developer view: raw JSON
                    </summary>

                    <pre className="story-raw-json">
                      {JSON.stringify(
                        selectedRun,
                        null,
                        2,
                      )}
                    </pre>
                  </details>

                  {selectedRun.error_message && (
                    <div className="error-panel">
                      {selectedRun.error_message}
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


export default InvestigationsWorkspace
