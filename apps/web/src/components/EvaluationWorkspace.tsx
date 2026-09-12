import {
  useEffect,
  useMemo,
  useState,
} from "react"

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
}


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
    <article className="evaluation-gauge-card">
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
    </article>
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


      <section className="evaluation-summary-strip">
        <article>
          <span>
            DATASET RECORDS
          </span>
          <strong>
            {summary.dataset.total_records}
          </strong>
        </article>

        <article>
          <span>
            UNIQUE SCENARIOS
          </span>
          <strong>
            {summary.dataset.unique_records}
          </strong>
        </article>

        <article>
          <span>
            DUPLICATES
          </span>
          <strong>
            {summary.dataset.duplicate_records}
          </strong>
        </article>

        <article>
          <span>
            FAILURES
          </span>
          <strong>
            {failures.failed_cases}
          </strong>
        </article>
      </section>


      <section className="evaluation-gauges">
        <AccuracyGauge
          title="Decision Accuracy"
          value={
            summary.metrics
              .decision_accuracy
          }
          detail="Business decision match"
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
        />

        <AccuracyGauge
          title="Human Review"
          value={
            summary.metrics
              .human_review_accuracy
          }
          detail="Review-routing accuracy"
        />
      </section>


      <section className="evaluation-visual-grid">

        <article className="evaluation-panel">
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
        </article>


        <article className="evaluation-panel">
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
        </article>
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

    </section>
  )
}


export default EvaluationWorkspace