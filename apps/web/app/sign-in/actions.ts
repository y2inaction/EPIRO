'use server'

import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

import { SESSION_COOKIE, SESSION_MAX_AGE_SECONDS } from '@/lib/session'

function apiUrl(): string {
  return process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
}

export interface SignInState {
  error?: string
}

/**
 * Exchange credentials for a session.
 *
 * The token is put straight into an httpOnly cookie and never returned to the
 * page. Page script cannot read it, so a cross-site scripting bug anywhere in
 * the application cannot steal it — which is the failure mode of keeping a
 * token in localStorage.
 *
 * The refresh token is deliberately discarded. It lives far longer than the
 * access token, and nothing in this interface refreshes a session: someone
 * signs in again after eight hours. Storing a long-lived credential we have no
 * use for would be taking a risk for nothing.
 */
export async function signIn(_state: SignInState, formData: FormData): Promise<SignInState> {
  const email = String(formData.get('email') ?? '').trim()
  const password = String(formData.get('password') ?? '')

  if (!email || !password) {
    return { error: 'Enter your email address and password.' }
  }

  let response: Response
  try {
    response = await fetch(`${apiUrl()}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ email, password }),
      cache: 'no-store',
    })
  } catch {
    return { error: 'The service could not be reached. Try again shortly.' }
  }

  if (response.status === 429) {
    return { error: 'Too many attempts. Wait a minute and try again.' }
  }

  if (!response.ok) {
    // Deliberately the same message whether the address is unknown or the
    // password is wrong: distinguishing them tells an attacker which accounts
    // exist.
    return { error: 'Those credentials were not accepted.' }
  }

  const body = (await response.json()) as { access_token?: string }
  if (!body.access_token) {
    return { error: 'The service returned an unusable response.' }
  }

  const store = await cookies()
  store.set(SESSION_COOKIE, body.access_token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: SESSION_MAX_AGE_SECONDS,
  })

  redirect('/workspace')
}

export async function signOut(): Promise<void> {
  const store = await cookies()
  store.delete(SESSION_COOKIE)
  redirect('/sign-in')
}
