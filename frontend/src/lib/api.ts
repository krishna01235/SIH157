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
}
export interface SubmissionListItem {
  id: string; entity_id: string; entity_name: string; label: string | null; period_start: string; period_end: string;
  alert_coverage: Coverage; synthetic: boolean; created_at: string; row_counts: Record<'assets' | 'alerts' | 'cases', number>;
}
export interface Page<T> { items: T[]; page: number; page_size: number; total: number }
export interface Overview { submissions: number; completed_assessments: number; awaiting_review: number }

export const api = {
  overview: () => request<Overview>('/overview'),
  entities: () => request<Entity[]>('/entities'),
  createEntity: (name: string, sector?: string) => request<Entity>('/entities', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, sector: sector || null }) }),
  submissions: (page = 1, pageSize = 25) => request<Page<SubmissionListItem>>(`/submissions?page=${page}&page_size=${pageSize}`),
  submission: (id: string) => request<Submission>(`/submissions/${encodeURIComponent(id)}`),
  importSubmission: (data: FormData) => request<Submission>('/submissions', { method: 'POST', body: data }),
}

export const formatDate = (value: string) => new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(value))
export const formatWindow = (start: string, end: string) => `${formatDate(start)} – ${formatDate(new Date(new Date(end).getTime() - 1).toISOString())}`
