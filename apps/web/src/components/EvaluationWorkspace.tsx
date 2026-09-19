import {
  useEffect,
  useMemo,
  useState,
} from "react"

import { createPortal } from "react-dom"

import {
  getEvaluationCases,
  getEvaluationFailures,
  getEvaluationStability,
  getEvaluationSummary,
  type EvaluationCaseResult,
  type EvaluationFailuresResponse,
  type EvaluationStabilityResponse,
  type EvaluationSummaryResponse,
} from "../lib/api"


interface AccuracyGaugeProps {
  title: string
  value: number
  detail: string
  onOpen: () => void
}


type InsightKey =
  | "scope"
  | "quality"
  | "stability"
  | "attention"
  | "records"
  | "unique"
  | "duplicates"
  | "failures"
  | "decision"
  | "credit"
  | "review"
  | "composition"
  | "repeatability"


function percent(
  value: number,
): string {
  return `${Math.round(value * 100)}%`
}


function humanize(
  value: string,
): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    )
}


function passed(
  item: EvaluationCaseResult,
): boolean {
  return (
    item.score.decision_correct &&
    item.score.human_review_correct &&
    item.score.credit_correct !== false
  )
}


function AccuracyGauge({
  title,
  value,
  detail,
  onOpen,
}: AccuracyGaugeProps) {
  const radius = 48
  const circumference =
    2 * Math.PI * radius

  const progress =
    Math.max(
      0,
      Math.min(
        1,
        value,
      ),
    )

  const dash =
    circumference * progress

  return (
    <button
      type="button"
      className="evaluation-gauge-card evaluation-clickable-card"
      onClick={onOpen}
    >
      <div className="evaluation-gauge">
        <svg
          viewBox="0 0 120 120"
          aria-hidden="true"
        >
          <circle
            className="evaluation-gauge-track"
            cx="60"
            cy="60"
            r={radius}
          />

          <circle
            className="evaluation-gauge-value"
            cx="60"
            cy="60"
            r={radius}
            strokeDasharray={
              `${dash} ${circumference - dash}`
            }
            transform="rotate(-90 60 60)"
          />
        </svg>

        <div className="evaluation-gauge-number">
          {percent(value)}
        </div>
      </div>

      <div className="evaluation-gauge-copy">
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
    </button>
  )
}


function EvaluationWorkspace() {
  const [
    summary,
    setSummary,
  ] = useState<EvaluationSummaryResponse | null>(
    null,
  )

  const [
    stability,
    setStability,
  ] = useState<EvaluationStabilityResponse | null>(
    null,
  )

  const [
    cases,
    setCases,
  ] = useState<EvaluationCaseResult[]>(
    [],
  )

  const [
    failures,
    setFailures,
  ] = useState<EvaluationFailuresResponse | null>(
    null,
  )

  const [
    loading,
    setLoading,
  ] = useState(
    true,
  )

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  )


  const [
    selectedInsight,
    setSelectedInsight,
  ] = useState<InsightKey>(
    "scope",
  )


  const [
    insightOpen,
    setInsightOpen,
  ] = useState(
    false,
  )


  useEffect(() => {
    if (!insightOpen) {
      return
    }

    const previousOverflow =
      document.body.style.overflow

    document.body.style.overflow =
      "hidden"

    function handleKeyDown(
      event: KeyboardEvent,
    ) {
      if (event.key === "Escape") {
        setInsightOpen(
          false,
        )
      }
    }

    window.addEventListener(
      "keydown",
      handleKeyDown,
    )

    return () => {
      document.body.style.overflow =
        previousOverflow

      window.removeEventListener(
        "keydown",
        handleKeyDown,
      )
    }
  }, [insightOpen])


  useEffect(() => {
    const controller =
      new AbortController()

    async function loadEvaluation() {
      try {
        setLoading(
          true,
        )

        setError(
          null,
        )

        const [
          summaryData,
          stabilityData,
          caseData,
          failureData,
        ] = await Promise.all([
          getEvaluationSummary(
            controller.signal,
          ),
          getEvaluationStability(
            controller.signal,
          ),
          getEvaluationCases(
            controller.signal,
          ),
          getEvaluationFailures(
            controller.signal,
          ),
        ])

        setSummary(
          summaryData,
        )

        setStability(
          stabilityData,
        )

        setCases(
          caseData,
        )

        setFailures(
          failureData,
        )
      } catch (caught) {
        if (
          caught instanceof DOMException &&
          caught.name === "AbortError"
        ) {
          return
        }

        setError(
          caught instanceof Error
            ? caught.message
            : "Unable to load evaluation evidence.",
        )
      } finally {
        setLoading(
          false,
        )
      }
    }

    void loadEvaluation()

    return () => {
      controller.abort()
    }
  }, [])


  const decisionDistribution =
    useMemo(
      () => {
        const counts =
          new Map<string, number>()

        cases.forEach(
          (item) => {
            counts.set(
              item.actual_decision,
              (
                counts.get(
                  item.actual_decision,
                ) ?? 0
              ) + 1,
            )
          },
        )

        return Array.from(
          counts.entries(),
        )
          .map(
            ([
              decision,
              count,
            ]) => ({
              decision,
              count,
            }),
          )
          .sort(
            (left, right) =>
              right.count -
              left.count,
          )
      },
      [
        cases,
      ],
    )


  const maxDecisionCount =
    Math.max(
      1,
      ...decisionDistribution.map(
        (item) => item.count,
      ),
    )


  if (loading) {
    return (
      <div className="evaluation-loading">
        Loading evaluation intelligence...
      </div>
    )
  }


  if (
    error ||
    !summary ||
    !stability ||
    !failures
  ) {
    return (
      <div className="error-panel">
        {error ??
          "Evaluation data unavailable."}
      </div>
    )
  }


  const uniqueShare =
    summary.dataset.total_records > 0
      ? (
          summary.dataset.unique_records /
          summary.dataset.total_records
        ) * 100
      : 0


  const insight =
    (() => {
      switch (selectedInsight) {
        case "quality":
          return {
            label: "DECISION QUALITY",
            title: "How well did the benchmark match expected outcomes?",
            summary:
              `Decision accuracy is ${percent(summary.metrics.decision_accuracy)}, human-review routing is ${percent(summary.metrics.human_review_accuracy)}, and credit accuracy is ${percent(summary.metrics.credit_accuracy)}.`,
            note:
              "These scores describe this deterministic benchmark only. They do not claim model generalization accuracy.",
          }

        case "stability":
        case "repeatability":
          return {
            label: "REPEATABILITY",
            title: "What does a stable baseline actually mean?",
            summary:
              `CaseMesh repeated the benchmark ${stability.repeated_runs} times and produced ${stability.unique_result_hashes} unique result-hash pattern(s).`,
            note:
              stability.stable
                ? "The same benchmark inputs produced consistent outputs across repeated runs."
                : "The repeated benchmark produced inconsistent outputs and should be investigated.",
          }

        case "attention":
        case "failures":
          return {
            label: "ATTENTION",
            title: "What should an operator review before trusting the benchmark?",
            summary:
              failures.failed_cases === 0
                ? "No failing benchmark cases are currently reported."
                : `${failures.failed_cases} benchmark case(s) failed and require review.`,
            note:
              "Duplicate records measure repeatability, not independent evidence. A clean deterministic run is useful, but it is not proof of broad model quality.",
          }

        case "records":
          return {
            label: "DATASET RECORDS",
            title: "Why are there more records than scenarios?",
            summary:
              `The benchmark contains ${summary.dataset.total_records} total records.`,
            note:
              `${summary.dataset.duplicate_records} records are repetitions used to test deterministic behavior across the same scenarios.`,
          }

        case "unique":
        case "composition":
          return {
            label: "UNIQUE SCENARIOS",
            title: "What is the independent scenario count?",
            summary:
              `${summary.dataset.unique_records} of ${summary.dataset.total_records} records are unique scenarios, which is ${Math.round(uniqueShare)}% of the dataset.`,
            note:
              "This is the more meaningful count when discussing scenario diversity.",
          }

        case "duplicates":
          return {
            label: "DUPLICATE RECORDS",
            title: "Why does CaseMesh intentionally repeat records?",
            summary:
              `${summary.dataset.duplicate_records} repeated records are included in the benchmark.`,
            note:
              "They test whether the system remains deterministic when the same scenario is executed repeatedly.",
          }

        case "decision":
          return {
            label: "DECISION ACCURACY",
            title: "Did CaseMesh choose the expected business decision?",
            summary:
              `Decision accuracy is ${percent(summary.metrics.decision_accuracy)} for this benchmark.`,
            note:
              "This compares actual benchmark decisions with the expected deterministic outcomes.",
          }

        case "credit":
          return {
            label: "CREDIT ACCURACY",
            title: "Did resolved credit cases match expected values?",
            summary:
              `Credit accuracy is ${percent(summary.metrics.credit_accuracy)} across ${summary.metrics.resolved_credit_cases} resolved credit cases.`,
            note:
              "This metric applies only to scenarios where credit resolution is part of the expected outcome.",
          }

        case "review":
          return {
            label: "HUMAN REVIEW ROUTING",
            title: "Did governance route cases to people correctly?",
            summary:
              `Human-review routing accuracy is ${percent(summary.metrics.human_review_accuracy)}.`,
            note:
              "This verifies whether the benchmark expected human intervention and whether CaseMesh routed the case accordingly.",
          }

        case "scope":
        default:
          return {
            label: "SCIENTIFIC SCOPE",
            title: "What does this dashboard prove, and what does it not prove?",
            summary:
              `CaseMesh evaluates ${summary.dataset.unique_records} unique scenarios across ${summary.dataset.total_records} total records.`,
            note:
              "The dashboard demonstrates deterministic SLA behavior, routing, and repeatability. It should not be presented as independent model-generalization evidence.",
          }
      }
    })()


  function openInsight(
    key: InsightKey,
  ) {
    setSelectedInsight(
      key,
    )

    setInsightOpen(
      true,
    )
  }


  return (
    <section className="evaluation-workspace">

      <section className="evaluation-hero">
        <div>
          <div className="section-label">
            AI EVALUATION CONTROL CENTER
          </div>

          <h2>
            Evaluation Intelligence
          </h2>

          <p>
            Deterministic SLA benchmark,
            repeatability evidence,
            scenario outcomes,
            and provenance in one
            operational view.
          </p>

          <div className="evaluation-run-id">
            <span>RUN</span>
            <strong>
              {summary.run_id}
            </strong>
          </div>
        </div>

        <div className="evaluation-hero-status">
          <div
            className={
              stability.stable
                ? "evaluation-live-dot stable"
                : "evaluation-live-dot unstable"
            }
          />

          <div>
            <span>
              DETERMINISTIC BASELINE
            </span>

            <strong>
              {stability.stable
                ? "STABLE"
                : "UNSTABLE"}
            </strong>
          </div>
        </div>
      </section>


      <section className="evaluation-scope-warning evaluation-dashboard-hint">
        <strong>
          Interactive dashboard
        </strong>

        <span>
          Click any card or gauge to open its explanation beside your current position. No scrolling back to the top.
        </span>
      </section>

      <section className="evaluation-scope-warning">
        <strong>
          Scientific scope
        </strong>

        <span>
          This benchmark contains{" "}
          {summary.dataset.total_records} records,
          but only{" "}
          {summary.dataset.unique_records} unique
          scenarios. The{" "}
          {summary.dataset.duplicate_records} duplicate
          records measure deterministic repetition,
          not independent evidence. These metrics are
          not model or generalization accuracy.
        </span>
      </section>


      <section className="evaluation-story-grid">
        <button type="button" className="story-card story-card-accent evaluation-clickable-card" onClick={() => openInsight("scope")}>
          <div className="story-step">
            01
          </div>

          <div className="section-label">
            WHAT WE TESTED
          </div>

          <h4>
            Benchmark scope
          </h4>

          <p className="story-copy">
            CaseMesh evaluated
            {" "}
            {summary.dataset.unique_records}
            {" "}
            unique scenario
            {summary.dataset.unique_records === 1
              ? ""
              : "s"}
            {" "}
            across
            {" "}
            {summary.dataset.total_records}
            {" "}
            total records.
          </p>
        </button>

        <button type="button" className="story-card evaluation-clickable-card" onClick={() => openInsight("quality")}>
          <div className="story-step">
            02
          </div>

          <div className="section-label">
            WHAT WORKED
          </div>

          <h4>
            Decision quality
          </h4>

          <p className="story-copy">
            Decision accuracy is
            {" "}
            {percent(
              summary.metrics
                .decision_accuracy,
            )}
            , human-review routing is
            {" "}
            {percent(
              summary.metrics
                .human_review_accuracy,
            )}
            , and credit accuracy is
            {" "}
            {percent(
              summary.metrics
                .credit_accuracy,
            )}
            .
          </p>
        </button>

        <button type="button" className="story-card evaluation-clickable-card" onClick={() => openInsight("stability")}>
          <div className="story-step">
            03
          </div>

          <div className="section-label">
            CAN WE REPEAT IT?
          </div>

          <h4>
            Stability story
          </h4>

          <p className="story-copy">
            {stability.stable
              ? `The baseline stayed stable across ${stability.repeated_runs} repeated runs with ${stability.unique_result_hashes} result hash pattern.`
              : "The repeated runs produced instability that should be investigated before relying on this baseline."}
          </p>
        </button>

        <button type="button" className="story-card story-next-action evaluation-clickable-card" onClick={() => openInsight("attention")}>
          <div className="story-step">
            04
          </div>

          <div className="section-label">
            WHAT NEEDS ATTENTION
          </div>

          <h4>
            Read the benchmark carefully
          </h4>

          <p className="story-copy">
            {failures.failed_cases === 0
              ? "No failing benchmark cases are currently reported. Duplicate records still measure repeatability, not independent model generalization."
              : `${failures.failed_cases} benchmark case(s) failed. Review the failure evidence before treating the baseline as ready.`}
          </p>
        </button>
      </section>

      <section className="evaluation-summary-strip">
        <button type="button" className="evaluation-summary-card evaluation-clickable-card" onClick={() => openInsight("records")}>
          <span>
            DATASET RECORDS
          </span>
          <strong>
            {summary.dataset.total_records}
          </strong>
        </button>

        <button type="button" className="evaluation-summary-card evaluation-clickable-card" onClick={() => openInsight("unique")}>
          <span>
            UNIQUE SCENARIOS
          </span>
          <strong>
            {summary.dataset.unique_records}
          </strong>
        </button>

        <button type="button" className="evaluation-summary-card evaluation-clickable-card" onClick={() => openInsight("duplicates")}>
          <span>
            DUPLICATES
          </span>
          <strong>
            {summary.dataset.duplicate_records}
          </strong>
        </button>

        <button type="button" className="evaluation-summary-card evaluation-clickable-card" onClick={() => openInsight("failures")}>
          <span>
            FAILURES
          </span>
          <strong>
            {failures.failed_cases}
          </strong>
        </button>
      </section>


      <section className="evaluation-gauges">
        <AccuracyGauge
          title="Decision Accuracy"
          value={
            summary.metrics
              .decision_accuracy
          }
          detail="Business decision match"
          onOpen={() => openInsight("decision")}
        />

        <AccuracyGauge
          title="Credit Accuracy"
          value={
            summary.metrics
              .credit_accuracy
          }
          detail={
            `${summary.metrics.resolved_credit_cases} resolved credit cases`
          }
          onOpen={() => openInsight("credit")}
        />

        <AccuracyGauge
          title="Human Review"
          value={
            summary.metrics
              .human_review_accuracy
          }
          detail="Review-routing accuracy"
          onOpen={() => openInsight("review")}
        />
      </section>


      <section className="evaluation-visual-grid">

        <button type="button" className="evaluation-panel evaluation-clickable-card" onClick={() => openInsight("composition")}>
          <div className="evaluation-panel-heading">
            <div>
              <div className="section-label">
                DATASET COMPOSITION
              </div>

              <h3>
                Evidence Shape
              </h3>
            </div>

            <strong>
              {summary.dataset.total_records}
            </strong>
          </div>

          <div className="dataset-composition">
            <div
              className="dataset-donut"
              style={{
                background:
                  `conic-gradient(
                    #6d8cff 0 ${uniqueShare}%,
                    #263249 ${uniqueShare}% 100%
                  )`,
              }}
            >
              <div className="dataset-donut-center">
                <strong>
                  {Math.round(
                    uniqueShare,
                  )}%
                </strong>

                <span>
                  unique
                </span>
              </div>
            </div>

            <div className="dataset-legend">
              <div>
                <span className="legend-dot unique" />
                <div>
                  <strong>
                    {summary.dataset.unique_records}
                  </strong>
                  <span>
                    Unique scenarios
                  </span>
                </div>
              </div>

              <div>
                <span className="legend-dot duplicate" />
                <div>
                  <strong>
                    {summary.dataset.duplicate_records}
                  </strong>
                  <span>
                    Duplicate records
                  </span>
                </div>
              </div>
            </div>
          </div>
        </button>


        <button type="button" className="evaluation-panel evaluation-clickable-card" onClick={() => openInsight("repeatability")}>
          <div className="evaluation-panel-heading">
            <div>
              <div className="section-label">
                DETERMINISTIC STABILITY
              </div>

              <h3>
                Repeatability Matrix
              </h3>
            </div>

            <strong>
              {stability.repeated_runs}/
              {stability.repeated_runs}
            </strong>
          </div>

          <div className="stability-run-grid">
            {Array.from({
              length:
                stability.repeated_runs,
            }).map(
              (
                _,
                index,
              ) => (
                <span
                  className={
                    stability.stable
                      ? "stability-run consistent"
                      : "stability-run warning"
                  }
                  key={index}
                  title={`Run ${index + 1}`}
                >
                  {String(
                    index + 1,
                  ).padStart(
                    2,
                    "0",
                  )}
                </span>
              ),
            )}
          </div>

          <div className="stability-summary">
            <div>
              <span>
                Executions
              </span>
              <strong>
                {stability.total_case_executions}
              </strong>
            </div>

            <div>
              <span>
                Result hashes
              </span>
              <strong>
                {stability.unique_result_hashes}
              </strong>
            </div>

            <div>
              <span>
                Scenarios / run
              </span>
              <strong>
                {stability.unique_scenarios_per_run}
              </strong>
            </div>
          </div>
        </button>
      </section>


      <section className="evaluation-panel">
        <div className="evaluation-panel-heading">
          <div>
            <div className="section-label">
              DECISION DISTRIBUTION
            </div>

            <h3>
              Benchmark Outcomes
            </h3>
          </div>

          <strong>
            {cases.length}
          </strong>
        </div>

        <div className="decision-distribution">
          {decisionDistribution.map(
            (item) => (
              <div
                className="decision-bar-row"
                key={item.decision}
              >
                <span>
                  {humanize(
                    item.decision,
                  )}
                </span>

                <div className="decision-bar-track">
                  <div
                    className="decision-bar-value"
                    style={{
                      width:
                        `${(
                          item.count /
                          maxDecisionCount
                        ) * 100}%`,
                    }}
                  />
                </div>

                <strong>
                  {item.count}
                </strong>
              </div>
            ),
          )}
        </div>
      </section>


      <section className="evaluation-panel scenario-panel">
        <div className="evaluation-panel-heading">
          <div>
            <div className="section-label">
              UNIQUE SCENARIOS
            </div>

            <h3>
              Scenario Matrix
            </h3>

            <p className="evaluation-panel-subtitle">
              {cases.length} unique benchmark scenarios
            </p>
          </div>

          <strong>
            {cases.length}
          </strong>
        </div>

        <div className="scenario-matrix">
          <div className="scenario-matrix-head">
            <span>Scenario</span>
            <span>Expected</span>
            <span>Actual</span>
            <span>Credit</span>
            <span>Review</span>
            <span>Result</span>
          </div>

          {cases.map(
            (item) => (
              <div
                className="scenario-matrix-row"
                key={item.fingerprint}
              >
                <div className="scenario-name">
                  <strong>
                    {humanize(
                      item.scenario_type,
                    )}
                  </strong>

                  <span>
                    {item.evaluation_id}
                  </span>
                </div>

                <span>
                  {humanize(
                    item.expected_decision,
                  )}
                </span>

                <span>
                  {humanize(
                    item.actual_decision,
                  )}
                </span>

                <span>
                  {item.actual_credit_pct === null
                    ? "Review"
                    : `${item.actual_credit_pct}%`}
                </span>

                <span>
                  {item.actual_human_review
                    ? "Required"
                    : "No"}
                </span>

                <span
                  className={
                    passed(
                      item,
                    )
                      ? "scenario-result pass"
                      : "scenario-result fail"
                  }
                >
                  {passed(
                    item,
                  )
                    ? "PASS"
                    : "FAIL"}
                </span>
              </div>
            ),
          )}
        </div>
      </section>


      <section className="evaluation-provenance">
        <div>
          <span>
            DATASET
          </span>
          <strong>
            {summary.provenance.dataset_name}
            {" "}
            v{summary.provenance.dataset_version}
          </strong>
        </div>

        <div>
          <span>
            PROFILE
          </span>
          <strong>
            {summary.provenance.benchmark_profile}
          </strong>
        </div>

        <div>
          <span>
            EVALUATOR
          </span>
          <strong>
            v{summary.provenance.evaluator_version}
          </strong>
        </div>

        <div>
          <span>
            SOURCE SHA
          </span>
          <strong>
            {summary.provenance.git_sha.slice(
              0,
              7,
            )}
          </strong>
        </div>

        <div>
          <span>
            TIMING
          </span>
          <strong>
            Local diagnostic only
          </strong>
        </div>
      </section>

      {insightOpen &&
        createPortal(
          <>
          <button
            type="button"
            className="evaluation-insight-backdrop"
            aria-label="Close metric details"
            onClick={() =>
              setInsightOpen(
                false,
              )
            }
          />

          <aside
            className="evaluation-insight-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="evaluation-insight-title"
          >
            <div className="evaluation-insight-drawer-head">
              <div>
                <div className="section-label">
                  {insight.label}
                </div>

                <h3 id="evaluation-insight-title">
                  {insight.title}
                </h3>
              </div>

              <button
                type="button"
                className="evaluation-insight-close"
                aria-label="Close details"
                onClick={() =>
                  setInsightOpen(
                    false,
                  )
                }
              >
                ×
              </button>
            </div>

            <div className="evaluation-insight-drawer-body">
              <section>
                <span className="evaluation-insight-kicker">
                  WHAT THIS MEANS
                </span>

                <p>
                  {insight.summary}
                </p>
              </section>

              <section>
                <span className="evaluation-insight-kicker">
                  HOW TO READ IT
                </span>

                <div className="evaluation-insight-note">
                  {insight.note}
                </div>
              </section>

              <div className="evaluation-insight-context">
                <span>
                  You can close this panel and keep your exact dashboard position.
                </span>

                <strong>
                  Press Esc or click outside to close.
                </strong>
              </div>
            </div>
          </aside>
        </>,
          document.body,
        )}

    </section>
  )
}


export default EvaluationWorkspace