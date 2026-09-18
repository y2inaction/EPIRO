'use client'

import { useActionState } from 'react'

import { signIn, type SignInState } from '@/app/sign-in/actions'

const FIELD =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600 ' +
  'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

const LABEL = 'block text-sm font-medium text-slate-800 dark:text-slate-200'

export default function SignInPage() {
  const [state, action, pending] = useActionState<SignInState, FormData>(signIn, {})

  return (
    <div className="mx-auto max-w-sm py-8">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
        Sign in
      </h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
        For staff recording and reviewing evidence. The public portal needs no
        account.
      </p>

      <form action={action} className="mt-8 space-y-5">
        {state.error ? (
          // role="alert" so the failure is announced, not only shown.
          <p
            role="alert"
            className="rounded-md bg-rose-50 p-3 text-sm text-rose-900 dark:bg-rose-950 dark:text-rose-100"
          >
            {state.error}
          </p>
        ) : null}

        <div className="space-y-1">
          <label htmlFor="email" className={LABEL}>
            Email address
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            required
            className={FIELD}
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="password" className={LABEL}>
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className={FIELD}
          />
        </div>

        <button
          type="submit"
          disabled={pending}
          className={
            'w-full rounded-md bg-slate-900 px-4 py-2 font-medium text-white transition ' +
            'hover:bg-slate-700 disabled:opacity-60 ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 ' +
            'dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white'
          }
        >
          {pending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
