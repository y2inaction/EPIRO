/**
 * Client for the public portal API.
 *
 * Only talks to /api/v1/public, which needs no credentials and serves only
 * published records. Nothing here sends a token, and nothing here can reach an
 * authenticated endpoint — that separation is deliberate, so a mistake in the
 * portal cannot expose internal data.
 *
 * The types mirror app/schemas/public.py exactly. They are allow-lists on that
 * side, so if a field is missing here it is because the API does not serve it.
 */

/**
 * Where the API lives.
 *
 * Read at request time, not at build time. Every caller in this file runs in a
 * server component, so `API_URL` is a genuine runtime lookup and one built
 * image can be pointed at staging or production by changing the environment.
 *
 * `NEXT_PUBLIC_API_URL` is kept as a fallback for existing deployments, but it
 * is inlined into the bundle at build time — setting only that one bakes the
 * address into the image permanently.
 */
function apiUrl(): string {
  return process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
}

/** How long a portal page may serve cached data before revalidating. */
const REVALIDATE_SECONDS = 60

export interface PublicOrganisation {
  id: string
  name: string
  code: string
}

export interface PublicStory {
  id: string
  title: string
  headline: string | null
  summary: string | null
  body: string
  language: string
  featured: boolean
  published_date: string | null
  evidence_reference: string | null
  organisation: PublicOrganisation | null
}

export interface PublicEvidence {
  id: string
  reference: string
  title: string
  description: string | null
  outcome: string | null
  evidence_date: string | null
  verification_status: string
  beneficiaries: number | null
  document_url: string | null
  tags: string[]
  organisation: PublicOrganisation | null
}

export interface PublicQuestion {
  id: string
  category: string | null
  question_text: string
  response: string | null
  response_date: string | null
  language: string
  organisation: PublicOrganisation | null
}

/**
 * A published finding about a claim that was circulating.
 *
 * Carries the reasoning as well as the verdict. A correction a reader cannot
 * check is an assertion, so `assessment` and `evidence_reference` are part of
 * what is published, not internal notes.
 *
 * Nobody is named — not the reviewers, and not whoever was repeating the
 * claim. `source` is a channel, as the API records it.
 */
export interface PublicCorrection {
  id: string
  claim: string
  finding: string
  assessment: string | null
  response: string | null
  source: string | null
  first_observed: string | null
  published_at: string | null
  language: string
  evidence_reference: string | null
  organisation: PublicOrganisation | null
}

export interface Page<T> {
  total: number
  page: number
  page_size: number
  total_pages: number
  data: T[]
}

export interface SearchResults {
  stories: PublicStory[]
  evidence: PublicEvidence[]
  questions: PublicQuestion[]
  corrections: PublicCorrection[]
  total: number
}

/**
 * The outcome of a request.
 *
 * A failure is a value rather than an exception because a portal page should
 * say that information is temporarily unavailable, not disappear. Pretending
 * an empty list came back when the API was unreachable would tell a reader
 * that a body has published nothing, which is a different and false claim.
 */
export type Result<T> =
  | { ok: true; value: T }
  | { ok: false; status: number | null; message: string }

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const rendered = search.toString()
  return rendered ? `?${rendered}` : ''
}

async function get<T>(path: string): Promise<Result<T>> {
  let response: Response
  try {
    response = await fetch(`${apiUrl()}/api/v1/public${path}`, {
      headers: { Accept: 'application/json' },
      next: { revalidate: REVALIDATE_SECONDS },
    })
  } catch {
    return {
      ok: false,
      status: null,
      message: 'The information service could not be reached.',
    }
  }

  if (response.status === 404) {
    return { ok: false, status: 404, message: 'Not found.' }
  }

  if (!response.ok) {
    return {
      ok: false,
      status: response.status,
      message: 'The information service returned an error.',
    }
  }

  try {
    return { ok: true, value: (await response.json()) as T }
  } catch {
    return {
      ok: false,
      status: response.status,
      message: 'The information service returned something unreadable.',
    }
  }
}

export interface ListOptions {
  page?: number
  pageSize?: number
  language?: string
  organisationId?: string
}

function paging(options: ListOptions) {
  const pageSize = options.pageSize ?? 12
  const page = Math.max(1, options.page ?? 1)
  return { limit: pageSize, skip: (page - 1) * pageSize }
}

export function listStories(
  options: ListOptions & { featuredOnly?: boolean } = {},
): Promise<Result<Page<PublicStory>>> {
  const { limit, skip } = paging(options)
  return get<Page<PublicStory>>(
    `/stories${query({
      limit,
      skip,
      language: options.language,
      featured_only: options.featuredOnly,
      organisation_id: options.organisationId,
    })}`,
  )
}

export function getStory(id: string): Promise<Result<PublicStory>> {
  return get<PublicStory>(`/stories/${encodeURIComponent(id)}`)
}

export function listEvidence(
  options: ListOptions = {},
): Promise<Result<Page<PublicEvidence>>> {
  const { limit, skip } = paging(options)
  return get<Page<PublicEvidence>>(
    `/evidence${query({ limit, skip, organisation_id: options.organisationId })}`,
  )
}

export function getEvidence(reference: string): Promise<Result<PublicEvidence>> {
  return get<PublicEvidence>(`/evidence/${encodeURIComponent(reference)}`)
}

export function listQuestions(
  options: ListOptions = {},
): Promise<Result<Page<PublicQuestion>>> {
  const { limit, skip } = paging(options)
  return get<Page<PublicQuestion>>(
    `/questions${query({
      limit,
      skip,
      language: options.language,
      organisation_id: options.organisationId,
    })}`,
  )
}

export function listCorrections(
  options: ListOptions = {},
): Promise<Result<Page<PublicCorrection>>> {
  const { limit, skip } = paging(options)
  return get<Page<PublicCorrection>>(
    `/corrections${query({
      limit,
      skip,
      language: options.language,
      organisation_id: options.organisationId,
    })}`,
  )
}

export function getCorrection(id: string): Promise<Result<PublicCorrection>> {
  return get<PublicCorrection>(`/corrections/${encodeURIComponent(id)}`)
}

export function search(term: string): Promise<Result<SearchResults>> {
  return get<SearchResults>(`/search${query({ q: term })}`)
}

export function listOrganisations(): Promise<Result<PublicOrganisation[]>> {
  return get<PublicOrganisation[]>('/organisations')
}
