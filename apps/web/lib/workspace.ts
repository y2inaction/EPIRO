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
