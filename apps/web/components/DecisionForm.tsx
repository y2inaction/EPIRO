'use client'

import { useActionState } from 'react'

import { applyDecision } from '@/app/workspace/decision-actions'
import type { TransitionState } from '@/app/workspace/content-actions'
import type { DecisionOffer } from '@/lib/decisions'

const BUTTON =
  'rounded-md px-4 py-2 text-sm font-medium transition disabled:opacity-60 ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600'

const PRIMARY =
  `${BUTTON} bg-slate-900 text-white hover:bg-slate-700 ` +
  'dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white'

const DESTRUCTIVE =
  `${BUTTON} border border-rose-300 text-rose-800 hover:bg-rose-50 ` +
  'dark:border-rose-800 dark:text-rose-200 dark:hover:bg-rose-950'

/** One thing a person may do to an action, with the field it requires. */
export function DecisionForm({
  actionId,
  offer,
}: {
  actionId: string
  offer: DecisionOffer
}) {
  const [state, submit, pending] = useActionState<TransitionState, FormData>(applyDecision, {})
  const fieldId = `${offer.name}-outcome`

  return (
    <form
      action={submit}
      className="space-y-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800"
    >
      <input type="hidden" name="action_id" value={actionId} />
      <input type="hidden" name="move" value={offer.name} />

      <div>
        <h3 className="font-medium text-slate-900 dark:text-slate-50">{offer.label}</h3>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{offer.hint}</p>
      </div>

      {offer.needsOutcome ? (
        <div className="space-y-1">
          <label
            htmlFor={fieldId}
            className="block text-xs font-medium text-slate-600 dark:text-slate-400"
          >
            What happened
          </label>
          <textarea
            id={fieldId}
            name="outcome"
            rows={3}
            required
            className={
              'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm ' +
              'text-slate-900 focus-visible:outline focus-visible:outline-2 ' +
              'focus-visible:outline-offset-2 focus-visible:outline-sky-600 ' +
              'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'
            }
          />
        </div>
      ) : null}

      <button type="submit" disabled={pending} className={offer.destructive ? DESTRUCTIVE : PRIMARY}>
        {pending ? 'Working…' : offer.label}
      </button>

      {state.error ? (
        <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">
          {state.error}
        </p>
      ) : null}
      {state.done ? (
        <p role="status" className="text-sm text-emerald-700 dark:text-emerald-300">
          {state.done}
        </p>
      ) : null}
    </form>
  )
}
