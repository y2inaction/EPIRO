/**
 * Client for the authenticated API.
 *
 * Separate from lib/api.ts, which only ever talks to the public endpoints.
 * Keeping them apart means a portal page cannot accidentally acquire a
 * credential, and a workspace page cannot accidentally lose one.
 *
 * Every function here runs on the server and reads the token from the session
 * cookie. None of it is importable into a client component without the build
 * failing, because `next/headers` is server-only.
 */

import { activeFilters, recordsQuery } from '@/lib/intelligence'
import type {
  Breakdown,
  ChangeFeed,
  FigureBasis,
  FilterSet,
  LabelMap,
  MeasureCatalogue,
  Overview,
  RecordPage,
} from '@/lib/intelligence'
import { readToken } from '@/lib/session'
import type { CurrentUser } from '@/lib/session'

function apiUrl(): string {
  return process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
}

export type Result<T> =
  | { ok: true; value: T }
  | { ok: false; status: number | null; message: string }

export interface Evidence {
  id: string
  reference: string
  title: string
  description: string | null
  outcome: string | null
  evidence_date: string | null
  beneficiaries: number | null
  organisation_id: string
  source_id: string
  status: string
  verification_status: string
  approval_status: string
  version: number
  created_at: string
  updated_at: string
}

export interface ApprovalRecord {
  id: string
  entity_type: string
  entity_id: string
  entity_version: number | null
  decision: string
  reviewer_id: string
  decided_at: string
  comments: string | null
}

export interface Page<T> {
  total: number
  page: number
  page_size: number
  total_pages: number
  data: T[]
}

/** The detail an API refusal carried, so a person can be told why. */
function detailOf(body: unknown): string | null {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
  }
  return null
}

async function request<T>(path: string, init: RequestInit = {}): Promise<Result<T>> {
  const token = await readToken()
  if (!token) {
    return { ok: false, status: 401, message: 'Your session has ended. Sign in again.' }
  }

  let response: Response
  try {
    response = await fetch(`${apiUrl()}/api/v1${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
      // Never cached: a workspace showing a stale approval state would invite
      // someone to act on a record that has already moved.
      cache: 'no-store',
    })
  } catch {
    return { ok: false, status: null, message: 'The service could not be reached.' }
  }

  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  if (!response.ok) {
    // The API's own message is the useful one: it says which role was needed,
    // or which rule the transition broke.
    return {
      ok: false,
      status: response.status,
      message: detailOf(body) ?? 'The action could not be completed.',
    }
  }

  return { ok: true, value: body as T }
}

export function getCurrentUser(): Promise<Result<CurrentUser>> {
  return request<CurrentUser>('/users/me')
}

export function listEvidence(
  organisationId: string,
  page = 1,
  pageSize = 20,
): Promise<Result<Page<Evidence>>> {
  const skip = (Math.max(1, page) - 1) * pageSize
  return request<Page<Evidence>>(
    `/evidence/?organisation_id=${encodeURIComponent(organisationId)}&skip=${skip}&limit=${pageSize}`,
  )
}

export function getEvidence(id: string): Promise<Result<Evidence>> {
  return request<Evidence>(`/evidence/${encodeURIComponent(id)}`)
}

export function listApprovals(evidenceId: string): Promise<Result<ApprovalRecord[]>> {
  return request<ApprovalRecord[]>(`/evidence/${encodeURIComponent(evidenceId)}/approvals`)
}

export function verifyEvidence(id: string, notes?: string): Promise<Result<Evidence>> {
  return request<Evidence>(`/evidence/${encodeURIComponent(id)}/verify`, {
    method: 'POST',
    body: JSON.stringify({ notes: notes ?? '' }),
  })
}

export function approveEvidence(id: string, comments?: string): Promise<Result<Evidence>> {
  return request<Evidence>(`/evidence/${encodeURIComponent(id)}/approve`, {
    method: 'POST',
    body: JSON.stringify({ comments: comments ?? null }),
  })
}

export function rejectEvidence(
  id: string,
  comments: string,
  changesRequested: boolean,
): Promise<Result<Evidence>> {
  return request<Evidence>(`/evidence/${encodeURIComponent(id)}/reject`, {
    method: 'POST',
    body: JSON.stringify({ comments, changes_requested: changesRequested }),
  })
}

export function publishEvidence(id: string): Promise<Result<Evidence>> {
  return request<Evidence>(`/evidence/${encodeURIComponent(id)}/publish`, { method: 'POST' })
}

export function withdrawEvidence(id: string, reason: string): Promise<Result<Evidence>> {
  return request<Evidence>(`/evidence/${encodeURIComponent(id)}/withdraw`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

// --- Stories ---------------------------------------------------------------

export interface Story {
  id: string
  title: string
  headline: string | null
  summary: string | null
  body: string
  language: string
  organisation_id: string
  evidence_id: string
  status: string
  featured: boolean
  published_date: string | null
  version: number
  created_at: string
  updated_at: string
}

export function listStories(language = 'en'): Promise<Result<Page<Story>>> {
  return request<Page<Story>>(`/stories/?language=${encodeURIComponent(language)}&limit=50`)
}

export function getStory(id: string): Promise<Result<Story>> {
  return request<Story>(`/stories/${encodeURIComponent(id)}`)
}

export function listStoryApprovals(id: string): Promise<Result<ApprovalRecord[]>> {
  return request<ApprovalRecord[]>(`/stories/${encodeURIComponent(id)}/approvals`)
}

export function submitStory(id: string): Promise<Result<Story>> {
  return request<Story>(`/stories/${encodeURIComponent(id)}/submit`, { method: 'POST' })
}

export function approveStory(id: string, comments?: string): Promise<Result<Story>> {
  return request<Story>(`/stories/${encodeURIComponent(id)}/approve`, {
    method: 'POST',
    body: JSON.stringify({ comments: comments ?? null }),
  })
}

export function rejectStory(
  id: string,
  comments: string,
  changesRequested: boolean,
): Promise<Result<Story>> {
  return request<Story>(`/stories/${encodeURIComponent(id)}/reject`, {
    method: 'POST',
    body: JSON.stringify({ comments, changes_requested: changesRequested }),
  })
}

export function publishStory(id: string): Promise<Result<Story>> {
  return request<Story>(`/stories/${encodeURIComponent(id)}/publish`, { method: 'POST' })
}

export function withdrawStory(id: string, reason: string): Promise<Result<Story>> {
  return request<Story>(`/stories/${encodeURIComponent(id)}/withdraw`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

// --- Questions -------------------------------------------------------------

export interface Question {
  id: string
  organisation_id: string | null
  category: string | null
  question_text: string
  location_state: string | null
  location_lga: string | null
  language: string
  is_anonymous: boolean
  status: string
  response: string | null
  response_date: string | null
  is_published: boolean
  created_at: string
  updated_at: string
}

/** The public inbox: questions nobody has claimed yet. */
export function listUntriagedQuestions(): Promise<Result<Page<Question>>> {
  return request<Page<Question>>('/questions/?untriaged=true&limit=50')
}

export function listQuestions(organisationId: string): Promise<Result<Page<Question>>> {
  return request<Page<Question>>(
    `/questions/?organisation_id=${encodeURIComponent(organisationId)}&limit=50`,
  )
}

export function getQuestion(id: string): Promise<Result<Question>> {
  return request<Question>(`/questions/${encodeURIComponent(id)}`)
}

export function listQuestionApprovals(id: string): Promise<Result<ApprovalRecord[]>> {
  return request<ApprovalRecord[]>(`/questions/${encodeURIComponent(id)}/approvals`)
}

export function triageQuestion(
  id: string,
  organisationId: string,
  category?: string,
): Promise<Result<Question>> {
  return request<Question>(`/questions/${encodeURIComponent(id)}/triage`, {
    method: 'POST',
    body: JSON.stringify({
      organisation_id: organisationId,
      category: category || null,
    }),
  })
}

export function respondToQuestion(id: string, response: string): Promise<Result<Question>> {
  return request<Question>(`/questions/${encodeURIComponent(id)}/respond`, {
    method: 'POST',
    body: JSON.stringify({ response }),
  })
}

export function approveQuestion(id: string, comments?: string): Promise<Result<Question>> {
  return request<Question>(`/questions/${encodeURIComponent(id)}/approve`, {
    method: 'POST',
    body: JSON.stringify({ comments: comments ?? null }),
  })
}

export function rejectQuestion(
  id: string,
  comments: string,
  changesRequested: boolean,
): Promise<Result<Question>> {
  return request<Question>(`/questions/${encodeURIComponent(id)}/reject`, {
    method: 'POST',
    body: JSON.stringify({ comments, changes_requested: changesRequested }),
  })
}

export function publishQuestion(id: string): Promise<Result<Question>> {
  return request<Question>(`/questions/${encodeURIComponent(id)}/publish`, { method: 'POST' })
}

// --- Intelligence ----------------------------------------------------------
//
// Read-only, and scoped by the server to every organisation the caller belongs
// to. There is no organisation parameter to pass: the API counts across the
// caller's tenants rather than one at a time, which the dashboard says out
// loud rather than implying otherwise with a selector that does nothing.

function query(filters: FilterSet = {}, extra: Record<string, string> = {}): string {
  return new URLSearchParams({ ...extra, ...activeFilters(filters) }).toString()
}

export function getOverview(filters: FilterSet = {}): Promise<Result<Overview>> {
  return request<Overview>(`/intelligence/overview?${query(filters)}`)
}

/** What is open, rather than how much has been done. */
export function getUnresolved(filters: FilterSet = {}): Promise<Result<Overview>> {
  return request<Overview>(`/intelligence/unresolved?${query(filters)}`)
}

export function getBreakdown(
  measure: string,
  dimension: string,
  filters: FilterSet = {},
): Promise<Result<Breakdown>> {
  return request<Breakdown>(`/intelligence/breakdown?${query(filters, { measure, dimension })}`)
}

/**
 * The records behind a figure.
 *
 * Takes the figure's own basis back, which is what makes a number on the
 * dashboard checkable rather than asserted.
 */
export function getRecords(
  basis: FigureBasis,
  page = 1,
  pageSize = 25,
): Promise<Result<RecordPage>> {
  const params = new URLSearchParams(recordsQuery(basis))
  params.set('skip', String((Math.max(1, page) - 1) * pageSize))
  params.set('limit', String(pageSize))

  return request<RecordPage>(`/intelligence/records?${params.toString()}`)
}

/**
 * What changed, when, to which record, and by whom.
 *
 * Note the date range means something different here — it narrows when the
 * change happened, not when the record was created. The response says so in
 * its own `date_note`, which the page shows rather than paraphrasing.
 */
export function getChanges(
  measure: string,
  filters: FilterSet = {},
  action?: string,
  page = 1,
  pageSize = 25,
): Promise<Result<ChangeFeed>> {
  const params = new URLSearchParams({ measure, ...activeFilters(filters) })
  if (action) {
    params.set('action', action)
  }
  params.set('skip', String((Math.max(1, page) - 1) * pageSize))
  params.set('limit', String(pageSize))

  return request<ChangeFeed>(`/intelligence/changes?${params.toString()}`)
}

export function listMeasures(): Promise<Result<MeasureCatalogue>> {
  return request<MeasureCatalogue>('/intelligence/measures')
}

export interface Named {
  id: string
  name: string
}

/**
 * Names for the buckets of a dimension that groups by identifier.
 *
 * A breakdown by area or theme comes back keyed on the column the server
 * grouped by, which is a UUID. These two lists are what turn that into
 * something a reader can act on.
 *
 * Capped at the API's own maximum page. A bucket whose identifier is not in
 * the page shows the identifier, and the panel says the name could not be
 * resolved — which is honest about the cap rather than quietly mislabelling
 * or dropping a real count.
 */
const NAME_SOURCE: Record<string, string> = {
  geography_id: '/geography/?limit=1000',
  thematic_area_id: '/thematic-areas/?limit=1000',
}

export async function listNamed(dimension: string): Promise<Named[]> {
  const path = NAME_SOURCE[dimension]
  if (!path) {
    return []
  }

  const result = await request<Page<Named>>(path)
  // A failed lookup leaves the identifiers showing. The counts are still
  // right, and the panel says the names are missing.
  return result.ok ? result.value.data : []
}

export async function namesFor(dimension: string): Promise<LabelMap> {
  const names: LabelMap = {}
  for (const item of await listNamed(dimension)) {
    names[item.id] = item.name
  }
  return names
}


// --- The decision register -------------------------------------------------

export interface ActionRecord {
  id: string
  organisation_id: string
  title: string
  rationale: string
  origin_type: string
  origin_id: string
  scenario_id: string | null
  owner_id: string
  status: string
  due_date: string | null
  started_at: string | null
  closed_at: string | null
  outcome: string | null
  /** Derived by the server on every read, never stored. */
  overdue: boolean
  created_at: string
  updated_at: string
}

export function listActions(params: {
  status?: string
  overdue?: string
} = {}): Promise<Result<Page<ActionRecord>>> {
  const query = new URLSearchParams({ limit: '100' })
  if (params.status) {
    query.set('status', params.status)
  }
  if (params.overdue) {
    query.set('overdue', params.overdue)
  }
  return request<Page<ActionRecord>>(`/actions/?${query.toString()}`)
}

export function getAction(id: string): Promise<Result<ActionRecord>> {
  return request<ActionRecord>(`/actions/${encodeURIComponent(id)}`)
}

export function acceptAction(id: string): Promise<Result<ActionRecord>> {
  return request<ActionRecord>(`/actions/${encodeURIComponent(id)}/accept`, { method: 'POST' })
}

export function startAction(id: string): Promise<Result<ActionRecord>> {
  return request<ActionRecord>(`/actions/${encodeURIComponent(id)}/start`, { method: 'POST' })
}

export function completeAction(id: string, outcome: string): Promise<Result<ActionRecord>> {
  return request<ActionRecord>(`/actions/${encodeURIComponent(id)}/complete`, {
    method: 'POST',
    body: JSON.stringify({ outcome }),
  })
}

export function dropAction(id: string, outcome: string): Promise<Result<ActionRecord>> {
  return request<ActionRecord>(`/actions/${encodeURIComponent(id)}/drop`, {
    method: 'POST',
    body: JSON.stringify({ outcome }),
  })
}
