import {
  apiScopes,
  msalInstance,
} from "../auth"


const rawBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.trim() || "/api"

export const API_BASE_URL =
  rawBaseUrl.replace(/\/$/, "")


export interface ApiRootResponse {
  service: string
  version: string
  status: string
  docs: string
  mcp?: string
}


export interface HealthReadyResponse {
  status: string
  database: string
}


export interface CaseRecord {
  id: string
  case_number: string
  title: string
  description: string | null
  status: string
  priority: string
  customer_ref: string | null
  created_at: string
  updated_at: string
}


export interface DocumentRecord {
  id: string
  case_id: string
  filename: string
  content_type: string | null
  sha256: string | null
  ingestion_status: string
  source_type: string
  size_bytes: number
  parser_name: string | null
  text_length: number | null
  ingested_at: string | null
  ingestion_error: string | null
  created_at: string
  updated_at: string
}


export interface DocumentChunkRecord {
  id: string
  document_id: string
  case_id: string
  chunk_index: number
  content: string
  char_count: number
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}


export interface DocumentEmbeddingResponse {
  case_id: string
  document_id: string
  provider: string
  model: string
  dimension: number
  chunks_embedded: number
}


export interface RetrievalResult {
  chunk_id: string
  document_id: string
  chunk_index: number
  content: string
  metadata_json: Record<string, unknown>
  hybrid_score: number
  vector_rank: number | null
  keyword_rank: number | null
  vector_similarity: number | null
  keyword_score: number | null
}


export interface RetrievalSearchResponse {
  query: string
  top_k: number
  mode: string
  embedding_model: string
  results: RetrievalResult[]
}


export type InvestigationState =
  | "created"
  | "running"
  | "completed"
  | "failed"


export type InvestigationConfidence =
  | "low"
  | "medium"
  | "high"


export interface InvestigationPlanStep {
  step: number
  title: string
}


export interface InvestigationEvidenceRef {
  chunk_id: string
  document_id: string
  chunk_index: number
  hybrid_score: number
  vector_rank: number | null
  keyword_rank: number | null
  excerpt: string
}


export interface InvestigationGap {
  code: string
  description: string
}


export interface InvestigationCitation {
  label: string
  chunk_id: string
  document_id: string
  chunk_index: number
  excerpt: string
}


export interface InvestigationRun {
  workflow_id: string
  case_id: string
  objective: string | null
  state: InvestigationState
  current_step: string | null
  attempt: number
  confidence: InvestigationConfidence | null
  abstained: boolean
  analysis: string | null
  assessment: string | null
  findings: string | null
  plan: InvestigationPlanStep[]
  evidence: InvestigationEvidenceRef[]
  gaps: InvestigationGap[]
  citations: InvestigationCitation[]
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}


export type ActionStatus =
  | "blocked"
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "auto_approved"
  | "executed"
  | "failed"


export type PolicyDecision =
  | "allow"
  | "require_approval"
  | "block"


export type RiskLevel =
  | "low"
  | "medium"
  | "high"
  | "critical"


export type ExecutionMode =
  | "dry_run"
  | "live"


export type ExecutionStatus =
  | "simulated"
  | "completed"
  | "replayed"


export interface PolicyEvaluation {
  decision: PolicyDecision
  risk_level: RiskLevel
  requires_human_approval: boolean
  rationale: string
}


export interface ActionRequestRecord {
  action_request_id: string
  case_id: string
  investigation_run_id: string | null
  resolution_draft_id: string | null
  approval_id: string | null
  thread_id: string | null
  action_type: string
  status: ActionStatus
  policy: PolicyEvaluation
  payload: Record<string, unknown>
  reviewed_payload: Record<string, unknown>
  approval_decision: string | null
  reviewer_ref: string | null
  approval_comment: string | null
  interrupt: Record<string, unknown> | null
  execution_enabled: boolean
  error_message: string | null
  created_at: string
  updated_at: string
}


export interface ActionExecutionRequest {
  mode: ExecutionMode
  idempotency_key: string
  requested_by: string
}


export interface ActionExecutionResponse {
  action_request_id: string
  case_id: string
  action_type: string
  mode: ExecutionMode
  status: ExecutionStatus
  idempotent_replay: boolean
  external_ref: string
  external_side_effect: boolean
  details: Record<string, unknown>
}


export interface AuditEventRecord {
  id: string
  case_id: string | null
  investigation_run_id: string | null
  action_request_id: string | null
  actor_type: string
  actor_ref: string | null
  event_type: string
  details: Record<string, unknown>
  created_at: string
}


export class ApiError extends Error {
  readonly status: number

  constructor(
    message: string,
    status: number,
  ) {
    super(message)

    this.name = "ApiError"
    this.status = status
  }
}


export async function getApiAccessToken():
Promise<string | null> {
  const activeAccount =
    msalInstance.getActiveAccount()

  const account =
    activeAccount ??
    msalInstance.getAllAccounts()[0]

  if (!account) {
    return null
  }

  if (!activeAccount) {
    msalInstance.setActiveAccount(
      account,
    )
  }

  try {
    const result =
      await msalInstance.acquireTokenSilent({
        account,
        scopes: apiScopes,
      })

    return result.accessToken
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unknown authentication error."

    throw new Error(
      `Unable to acquire CaseMesh API access token. ${message}`,
    )
  }
}


async function parseApiError(
  response: Response,
): Promise<never> {
  let detail = ""

  try {
    const payload =
      (await response.json()) as {
        detail?:
          | string
          | {
              message?: string
              workflow_id?: string
              action_request_id?: string
            }
      }

    if (
      typeof payload.detail === "string"
    ) {
      detail =
        ` ${payload.detail}`
    } else if (
      payload.detail?.message
    ) {
      detail =
        ` ${payload.detail.message}`
    }
  } catch {
    detail = ""
  }

  throw new ApiError(
    `API request failed with status ${response.status}.${detail}`,
    response.status,
  )
}


async function publicRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers =
    new Headers(
      init?.headers,
    )

  headers.set(
    "Accept",
    "application/json",
  )

  const response =
    await fetch(
      `${API_BASE_URL}${path}`,
      {
        ...init,
        headers,
      },
    )

  if (!response.ok) {
    return parseApiError(
      response,
    )
  }

  return (
    await response.json()
  ) as T
}


async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const accessToken =
    await getApiAccessToken()

  const headers =
    new Headers(
      init?.headers,
    )

  headers.set(
    "Accept",
    "application/json",
  )

  if (accessToken) {
    headers.set(
      "Authorization",
      `Bearer ${accessToken}`,
    )
  }

  const response =
    await fetch(
      `${API_BASE_URL}${path}`,
      {
        ...init,
        headers,
      },
    )

  if (!response.ok) {
    return parseApiError(
      response,
    )
  }

  return (
    await response.json()
  ) as T
}


export function getHealthReady(
  signal?: AbortSignal,
): Promise<HealthReadyResponse> {
  return publicRequest<HealthReadyResponse>(
    "/health/ready",
    {
      signal,
    },
  )
}


export function getApiRoot(
  signal?: AbortSignal,
): Promise<ApiRootResponse> {
  return request<ApiRootResponse>(
    "/",
    {
      signal,
    },
  )
}


export function getCases(
  signal?: AbortSignal,
): Promise<CaseRecord[]> {
  return request<CaseRecord[]>(
    "/cases",
    {
      signal,
    },
  )
}


export function getCase(
  caseId: string,
  signal?: AbortSignal,
): Promise<CaseRecord> {
  return request<CaseRecord>(
    `/cases/${caseId}`,
    {
      signal,
    },
  )
}


export function getDocuments(
  caseId: string,
  signal?: AbortSignal,
): Promise<DocumentRecord[]> {
  return request<DocumentRecord[]>(
    `/cases/${caseId}/documents`,
    {
      signal,
    },
  )
}


export function getDocumentChunks(
  caseId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentChunkRecord[]> {
  return request<DocumentChunkRecord[]>(
    `/cases/${caseId}/documents/${documentId}/chunks`,
    {
      signal,
    },
  )
}


export function uploadDocument(
  caseId: string,
  file: File,
): Promise<DocumentRecord> {
  const formData =
    new FormData()

  formData.append(
    "file",
    file,
  )

  return request<DocumentRecord>(
    `/cases/${caseId}/documents`,
    {
      method: "POST",
      body: formData,
    },
  )
}


export function ingestDocument(
  caseId: string,
  documentId: string,
): Promise<DocumentRecord> {
  return request<DocumentRecord>(
    `/cases/${caseId}/documents/${documentId}/ingest`,
    {
      method: "POST",
    },
  )
}


export function embedDocument(
  caseId: string,
  documentId: string,
): Promise<DocumentEmbeddingResponse> {
  return request<DocumentEmbeddingResponse>(
    `/cases/${caseId}/documents/${documentId}/embed`,
    {
      method: "POST",
    },
  )
}


export function searchEvidence(
  caseId: string,
  query: string,
  topK = 5,
): Promise<RetrievalSearchResponse> {
  return request<RetrievalSearchResponse>(
    `/cases/${caseId}/retrieval/search`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify({
        query,
        top_k: topK,
      }),
    },
  )
}


export function getInvestigations(
  caseId: string,
  signal?: AbortSignal,
): Promise<InvestigationRun[]> {
  return request<InvestigationRun[]>(
    `/cases/${caseId}/investigations`,
    {
      signal,
    },
  )
}


export function getInvestigation(
  caseId: string,
  workflowId: string,
  signal?: AbortSignal,
): Promise<InvestigationRun> {
  return request<InvestigationRun>(
    `/cases/${caseId}/investigations/${workflowId}`,
    {
      signal,
    },
  )
}


export function startInvestigation(
  caseId: string,
  objective: string,
): Promise<InvestigationRun> {
  return request<InvestigationRun>(
    `/cases/${caseId}/investigations`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify({
        objective,
      }),
    },
  )
}


export function getActions(
  caseId: string,
  signal?: AbortSignal,
): Promise<ActionRequestRecord[]> {
  return request<ActionRequestRecord[]>(
    `/cases/${caseId}/actions`,
    {
      signal,
    },
  )
}


export function getAction(
  caseId: string,
  actionRequestId: string,
  signal?: AbortSignal,
): Promise<ActionRequestRecord> {
  return request<ActionRequestRecord>(
    `/cases/${caseId}/actions/${actionRequestId}`,
    {
      signal,
    },
  )
}


export function decideAction(
  caseId: string,
  actionRequestId: string,
  decision: "approve" | "reject",
  reviewerRef: string,
  comment: string | null,
): Promise<ActionRequestRecord> {
  return request<ActionRequestRecord>(
    `/cases/${caseId}/actions/${actionRequestId}/decision`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify({
        decision,
        reviewer_ref: reviewerRef,
        comment,
      }),
    },
  )
}


export function executeAction(
  caseId: string,
  actionRequestId: string,
  mode: ExecutionMode,
  idempotencyKey: string,
  requestedBy: string,
): Promise<ActionExecutionResponse> {
  const payload:
  ActionExecutionRequest = {
    mode,
    idempotency_key:
      idempotencyKey,
    requested_by:
      requestedBy,
  }

  return request<ActionExecutionResponse>(
    `/cases/${caseId}/actions/${actionRequestId}/execute`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(
        payload,
      ),
    },
  )
}


export function getActionAuditEvents(
  caseId: string,
  actionRequestId: string,
  signal?: AbortSignal,
): Promise<AuditEventRecord[]> {
  return request<AuditEventRecord[]>(
    `/cases/${caseId}/actions/${actionRequestId}/audit-events`,
    {
      signal,
    },
  )
}


export interface EvaluationMetricSummary {
  evaluated_cases: number
  resolved_credit_cases: number
  decision_accuracy: number
  credit_accuracy: number
  human_review_accuracy: number
}


export interface EvaluationDatasetSummary {
  total_records: number
  unique_records: number
  duplicate_records: number
  duplicate_groups: number
}


export interface EvaluationProvenance {
  dataset_name: string
  dataset_version: string
  dataset_fingerprint: string
  benchmark_profile: string
  resolution_engine: string
  provider: string
  model: string | null
  evaluator_version: string
  git_sha: string
  source_tree_dirty: boolean
}


export interface EvaluationSummaryResponse {
  run_id: string
  created_at: string
  provenance: EvaluationProvenance
  dataset: EvaluationDatasetSummary
  evaluated_cases: number
  failed_cases: number
  metrics: EvaluationMetricSummary
}


export interface EvaluationCaseScore {
  decision_correct: boolean
  credit_correct: boolean | null
  human_review_correct: boolean
}


export interface EvaluationCaseResult {
  evaluation_id: string
  scenario_type: string
  fingerprint: string
  expected_decision: string
  actual_decision: string
  expected_credit_pct: number | null
  actual_credit_pct: number | null
  expected_human_review: boolean
  actual_human_review: boolean
  score: EvaluationCaseScore
}


export interface EvaluationFailuresResponse {
  run_id: string
  created_at: string
  provenance: EvaluationProvenance
  failed_cases: number
  cases: EvaluationCaseResult[]
}


export interface EvaluationStabilityResponse {
  repeated_runs: number
  unique_scenarios_per_run: number
  total_case_executions: number
  unique_result_hashes: number
  decision_stability: number
  credit_stability: number
  human_review_stability: number
  stable: boolean
  timing_scope: string
}


export function getEvaluationSummary(
  signal?: AbortSignal,
): Promise<EvaluationSummaryResponse> {
  return request<EvaluationSummaryResponse>(
    "/evaluation/summary",
    { signal },
  )
}


export function getEvaluationStability(
  signal?: AbortSignal,
): Promise<EvaluationStabilityResponse> {
  return request<EvaluationStabilityResponse>(
    "/evaluation/stability",
    { signal },
  )
}


export function getEvaluationCases(
  signal?: AbortSignal,
): Promise<EvaluationCaseResult[]> {
  return request<EvaluationCaseResult[]>(
    "/evaluation/cases",
    { signal },
  )
}


export function getEvaluationFailures(
  signal?: AbortSignal,
): Promise<EvaluationFailuresResponse> {
  return request<EvaluationFailuresResponse>(
    "/evaluation/failures",
    { signal },
  )
}
