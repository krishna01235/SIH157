export type Coverage = 'complete' | 'sample' | 'unknown'
export type ReviewStatus = 'needs_review' | 'confirmed' | 'dismissed' | 'needs_context'

export interface ApiDetail { file?: string; row?: number | null; field?: string; message?: string; existing_id?: string }
export class ApiError extends Error {
  code: string
  status: number
  details: ApiDetail[]
  constructor(code: string, message: string, status: number, details: ApiDetail[] = []) {
    super(message)
    this.code = code
    this.status = status
    this.details = details
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(`/api/v1${path}`, options) }
  catch { throw new ApiError('network_error', 'The workbench could not reach the server. Check the connection and try again.', 0) }
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const issue = payload?.error
    throw new ApiError(issue?.code ?? 'request_failed', issue?.message ?? 'The request failed. Try again.', response.status, issue?.details ?? [])
  }
  return payload as T
}

export interface Entity { id: string; name: string; sector: string | null }
export interface SourceFile { kind: string; display_name: string; sha256: string; byte_size: number; row_count: number }
export interface Submission {
  id: string; entity_id: string; entity_name: string; label: string | null; period_start: string; period_end: string;
  alert_coverage: Coverage; dataset_hash: string; synthetic: boolean; created_at: string;
  validation_summary: { row_counts: Record<'assets' | 'alerts' | 'cases', number>; warnings: string[] };
  source_files: SourceFile[]; reused?: boolean;
  latest_run_id?: string | null; latest_run_status?: string | null;
}
export interface SubmissionListItem {
  id: string; entity_id: string; entity_name: string; label: string | null; period_start: string; period_end: string;
  alert_coverage: Coverage; synthetic: boolean; created_at: string; row_counts: Record<'assets' | 'alerts' | 'cases', number>;
  latest_run_id: string | null; latest_run_status: string | null;
}
export interface Page<T> { items: T[]; page: number; page_size: number; total: number }
export interface Overview { submissions: number; completed_assessments: number; awaiting_review: number }
export type CheckStatus = 'signal' | 'no_signal' | 'not_evaluable'
export interface CheckResult { rule_id: string; rule_version: string; title: string; status: CheckStatus; evaluated_count: number; affected_count: number; unknown_count: number; excluded_count: number; parameters: Record<string, number | string>; reason: string | null; rationale: string; finding_id: string | null }
export interface AssessmentRun { id: string; submission_id: string; engine_version: string; config_hash: string; configuration: Record<string, unknown>; input_hash: string; status: 'running' | 'completed' | 'failed'; error_code: string | null; created_at: string; finished_at: string | null; finding_count: number; awaiting_review_count: number; checks: CheckResult[]; reused?: boolean }
export interface FindingSummary { id: string; run_id: string; rule_id: string; title: string; rationale: string; review_status: ReviewStatus; review_note: string; revision: number; updated_at: string; evaluated_count: number; affected_count: number; unknown_count: number }
export interface FindingDetail extends FindingSummary { submission_id: string; rule_version: string; status: CheckStatus; parameters: Record<string, number | string>; excluded_count: number; alert_coverage: Coverage; period_start: string; period_end: string; dataset_hash: string; config_hash: string; history: ReviewEvent[] }
export interface ReviewEvent { id: string; prior_status: ReviewStatus; new_status: ReviewStatus; prior_note: string; new_note: string; operator_label: string; created_at: string; revision: number }
export interface Evidence { id: string; kind: 'asset' | 'case' | 'alert'; role: string; source_id: string; source_row: number; source_file: string; source_file_sha256: string; fields: Record<string, string>; duration_seconds?: number | null }

export const api = {
  overview: () => request<Overview>('/overview'),
  entities: () => request<Entity[]>('/entities'),
  createEntity: (name: string, sector?: string) => request<Entity>('/entities', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, sector: sector || null }) }),
  submissions: (page = 1, pageSize = 25) => request<Page<SubmissionListItem>>(`/submissions?page=${page}&page_size=${pageSize}`),
  submission: (id: string) => request<Submission>(`/submissions/${encodeURIComponent(id)}`),
  importSubmission: (data: FormData) => request<Submission>('/submissions', { method: 'POST', body: data }),
  loadDemo: () => request<{ submissions: { entity_id: string; submission_id: string; run_id: string }[] }>('/demo', { method: 'POST' }),
  runAssessment: (submissionId: string) => request<AssessmentRun>(`/submissions/${encodeURIComponent(submissionId)}/runs`, { method: 'POST' }),
  run: (runId: string) => request<AssessmentRun>(`/runs/${encodeURIComponent(runId)}`),
  findings: (runId: string, page = 1, ruleId = '', status = '') => request<Page<FindingSummary>>(`/runs/${encodeURIComponent(runId)}/findings?${new URLSearchParams({ page: String(page), page_size: '25', ...(ruleId ? { rule_id: ruleId } : {}), ...(status ? { status } : {}) })}`),
  finding: (findingId: string) => request<FindingDetail>(`/findings/${encodeURIComponent(findingId)}`),
  evidence: (findingId: string, page = 1) => request<Page<Evidence>>(`/findings/${encodeURIComponent(findingId)}/evidence?page=${page}&page_size=25`),
}

export const parseUtc = (value: string) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
export const formatDate = (value: string) => new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(parseUtc(value))
export const formatWindow = (start: string, end: string) => `${formatDate(start)} – ${formatDate(new Date(parseUtc(end).getTime() - 1).toISOString())}`
