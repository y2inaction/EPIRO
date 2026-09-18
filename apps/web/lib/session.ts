import { cookies } from 'next/headers'

/**
 * The signed-in session.
 *
 * The access token lives in an httpOnly cookie. Page script cannot read it, so
 * a cross-site scripting bug in any component cannot walk off with a
 * credential — which is exactly what happens when a token is kept in
 * localStorage, where every script on the page can reach it.
 *
 * The consequence is that every authenticated call happens on the server. That
 * is a constraint worth having: it also means the browser never learns the API
 * address, and a client-side mistake cannot call an endpoint the caller should
 * not reach.
 */
export const SESSION_COOKIE = 'epiro_session'

/** Eight hours: a working day, after which someone signs in again. */
export const SESSION_MAX_AGE_SECONDS = 8 * 60 * 60

export async function readToken(): Promise<string | null> {
  const store = await cookies()
  return store.get(SESSION_COOKIE)?.value ?? null
}

export interface OrganisationMembership {
  organisation_id: string
  name: string
  code: string
  role: string
}

export interface CurrentUser {
  id: string
  email: string
  first_name: string
  last_name: string
  memberships: OrganisationMembership[]
}

/**
 * Role groups, mirroring app/authorization.py.
 *
 * These decide which actions the interface *offers*. They are not the
 * authorisation: the server checks every call again and is the only thing that
 * can actually refuse one. Keeping them in step matters for honesty rather
 * than safety — offering a button that always fails wastes someone's time and
 * makes the system look broken.
 */
export const EVIDENCE_AUTHORS = ['researcher', 'field_officer', 'evidence_manager', 'editor']
export const EVIDENCE_VERIFIERS = ['verifier', 'evidence_manager']
export const APPROVERS = ['approver', 'executive']
export const PUBLISHERS = ['content_manager', 'editor']

/** SUPER_ADMIN carries full rights, but only inside its own organisation. */
export function holds(role: string | undefined, allowed: string[]): boolean {
  if (!role) {
    return false
  }
  return role === 'super_admin' || allowed.includes(role)
}

export function roleIn(user: CurrentUser, organisationId: string): string | undefined {
  return user.memberships.find((m) => m.organisation_id === organisationId)?.role
}
