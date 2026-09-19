'use client'

import { useActionState } from 'react'

import type { TransitionState } from '@/app/workspace/content-actions'
import { raiseDecision } from '@/app/workspace/decision-actions'

const FIELD =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600 ' +
  'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

const LABEL = 'block text-sm font-medium text-slate-900 dark:text-slate-100'
const HINT = 'mt-1 text-xs text-slate-600 dark:text-slate-400'

export interface OriginGroup {
  label: string
  options: { value: string; label: string }[]
}

/**
 * Raise a decision against something the organisation already holds.
 *
 * The origin is one select rather than two linked ones, so the form needs no
 * scripting to work. Candidates come from the intelligence drill-down, which
 * is already scoped exactly as the dashboard is.
 */
export function RaiseDecisionForm({
  organisationId,
  ownerId,
  ownerName,
  groups,
}: {
  organisationId: string
  ownerId: string
  ownerName: string
  groups: OriginGroup[]
}) {
  const [state, submit, pending] = useActionState<TransitionState, FormData>(raiseDecision, {})
  const empty = groups.every((group) => group.options.length === 0)

  return (
    <form action={submit} className="max-w-2xl space-y-6">
      <input type="hidden" name="organisation_id" value={organisationId} />
      <input type="hidden" name="owner_id" value={ownerId} />

      <div>
        <label className={LABEL} htmlFor="origin">
          What prompted this
        </label>
        <p className={HINT}>
          Required. An action nobody can trace back to a finding is a wish list, and the
          server refuses one whose origin it cannot find.
        </p>
        <select id="origin" name="origin" required disabled={empty} className={`${FIELD} mt-2`}>
          <option value="">Choose a record…</option>
          {groups.map((group) =>
            group.options.length === 0 ? null : (
              <optgroup key={group.label} label={group.label}>
                {group.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </optgroup>
            ),
          )}
        </select>
        {empty ? (
          <p className="mt-2 text-sm text-amber-800 dark:text-amber-200">
            There is nothing to raise an action against yet. Record a signal, a scenario or
            an evidence record first.
          </p>
        ) : null}
      </div>

      <div>
        <label className={LABEL} htmlFor="title">
          What will be done
        </label>
        <input id="title" name="title" required maxLength={255} className={`${FIELD} mt-2`} />
      </div>

      <div>
        <label className={LABEL} htmlFor="rationale">
          Why it follows from that
        </label>
        <p className={HINT}>
          Required. The reasoning is what a reviewer needs and the part nobody can
          reconstruct afterwards.
        </p>
        <textarea id="rationale" name="rationale" rows={4} required className={`${FIELD} mt-2`} />
      </div>

      <div>
        <label className={LABEL} htmlFor="due_date">
          Due by (optional)
        </label>
        <input type="date" id="due_date" name="due_date" className={`${FIELD} mt-2`} />
      </div>

      <p className="text-sm text-slate-600 dark:text-slate-400">
        You will own this ({ownerName}). Somebody else records it as done or dropped — the
        owner does the work, and a second person says it happened.
      </p>

      <button
        type="submit"
        disabled={pending || empty}
        className={
          'rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition ' +
          'hover:bg-slate-700 disabled:opacity-60 ' +
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
          'focus-visible:outline-sky-600 ' +
          'dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white'
        }
      >
        {pending ? 'Raising…' : 'Raise it'}
      </button>

      {state.error ? (
        <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">
          {state.error}
        </p>
      ) : null}
    </form>
  )
}
