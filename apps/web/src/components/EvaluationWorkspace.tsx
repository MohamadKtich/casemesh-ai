import { useEffect, useState } from "react"

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


function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}


function label(value: string): string {
  return value.replaceAll("_", " ")
}


function EvaluationWorkspace() {
  const [summary, setSummary] = useState<EvaluationSummaryResponse | null>(null)
  const [stability, setStability] = useState<EvaluationStabilityResponse | null>(null)
  const [cases, setCases] = useState<EvaluationCaseResult[]>([])
  const [failures, setFailures] = useState<EvaluationFailuresResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    async function loadEvaluation() {
      try {
        setLoading(true)
        setError(null)

        const [summaryData, stabilityData, caseData, failureData] =
          await Promise.all([
            getEvaluationSummary(controller.signal),
            getEvaluationStability(controller.signal),
            getEvaluationCases(controller.signal),
            getEvaluationFailures(controller.signal),
          ])

        setSummary(summaryData)
        setStability(stabilityData)
        setCases(caseData)
        setFailures(failureData)
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return
        }

        setError(
          caught instanceof Error
            ? caught.message
            : "Unable to load evaluation evidence.",
        )
      } finally {
        setLoading(false)
      }
    }

    void loadEvaluation()

    return () => controller.abort()
  }, [])

  if (loading) {
    return <div className="empty-state">Loading evaluation evidence...</div>
  }

  if (error || !summary || !stability || !failures) {
    return <div className="error-panel">{error ?? "Evaluation data unavailable."}</div>
  }

  return (
    <section className="evaluation-workspace">
      <div className="workspace-header">
        <div>
          <div className="section-label">BENCHMARK EVIDENCE</div>
          <h2>Evaluation Dashboard</h2>
          <p>
            Deterministic SLA benchmark evidence from the deployed CaseMesh evaluation pipeline.
          </p>
        </div>

        <span className={`evaluation-state ${stability.stable ? "stable" : "unstable"}`}>
          {stability.stable ? "Stable" : "Unstable"}
        </span>
      </div>

      <div className="evaluation-notice">
        <strong>Benchmark scope:</strong> {summary.dataset.total_records} dataset records contain{" "}
        {summary.dataset.unique_records} unique scenarios and{" "}
        {summary.dataset.duplicate_records} duplicate records. Accuracy reflects the deterministic
        SLA rule engine on the unique scenarios, not model or generalization accuracy.
      </div>

      <div className="evaluation-metrics-grid">
        <article className="metric-card"><div className="metric-label">UNIQUE SCENARIOS</div><div className="metric-value">{summary.dataset.unique_records}</div><div className="metric-detail">{summary.evaluated_cases} evaluated</div></article>
        <article className="metric-card"><div className="metric-label">DECISION ACCURACY</div><div className="metric-value">{percent(summary.metrics.decision_accuracy)}</div><div className="metric-detail">Business decision match</div></article>
        <article className="metric-card"><div className="metric-label">CREDIT ACCURACY</div><div className="metric-value">{percent(summary.metrics.credit_accuracy)}</div><div className="metric-detail">{summary.metrics.resolved_credit_cases} resolved credit cases</div></article>
        <article className="metric-card"><div className="metric-label">HUMAN REVIEW</div><div className="metric-value">{percent(summary.metrics.human_review_accuracy)}</div><div className="metric-detail">Review-routing accuracy</div></article>
        <article className="metric-card"><div className="metric-label">FAILED CASES</div><div className="metric-value">{summary.failed_cases}</div><div className="metric-detail">Current baseline</div></article>
      </div>

      <div className="evaluation-grid">
        <article className="workspace-card">
          <div className="section-label">STABILITY</div>
          <h3>Repeatability</h3>
          <div className="evaluation-stat-list">
            <div><span>Repeated runs</span><strong>{stability.repeated_runs}</strong></div>
            <div><span>Unique scenarios / run</span><strong>{stability.unique_scenarios_per_run}</strong></div>
            <div><span>Deterministic executions</span><strong>{stability.total_case_executions}</strong></div>
            <div><span>Unique result hashes</span><strong>{stability.unique_result_hashes}</strong></div>
          </div>
        </article>

        <article className="workspace-card">
          <div className="section-label">PROVENANCE</div>
          <h3>Benchmark Identity</h3>
          <div className="evaluation-stat-list">
            <div><span>Dataset</span><strong>{summary.provenance.dataset_name} v{summary.provenance.dataset_version}</strong></div>
            <div><span>Profile</span><strong>{summary.provenance.benchmark_profile}</strong></div>
            <div><span>Evaluator</span><strong>v{summary.provenance.evaluator_version}</strong></div>
            <div><span>Source</span><strong>{summary.provenance.git_sha.slice(0, 7)}</strong></div>
          </div>
        </article>
      </div>

      <div className="evaluation-table">
        <div className="evaluation-table-head">
          <span>Scenario</span><span>Expected</span><span>Actual</span><span>Credit</span><span>Result</span>
        </div>

        {cases.map((item) => (
          <div className="evaluation-row" key={item.fingerprint}>
            <div><strong>{label(item.scenario_type)}</strong><span>{item.evaluation_id}</span></div>
            <span>{label(item.expected_decision)}</span>
            <span>{label(item.actual_decision)}</span>
            <span>{item.actual_credit_pct === null ? "Review" : `${item.actual_credit_pct}%`}</span>
            <span className={`evaluation-result ${item.score.decision_correct ? "pass" : "fail"}`}>
              {item.score.decision_correct ? "PASS" : "FAIL"}
            </span>
          </div>
        ))}
      </div>

      <div className="evaluation-footer-note">
        {failures.failed_cases === 0
          ? "No benchmark failures in the persisted baseline."
          : `${failures.failed_cases} benchmark failures require review.`}
      </div>
    </section>
  )
}


export default EvaluationWorkspace
