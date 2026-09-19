'use client'

import { useActionState } from 'react'

import {
  applyQuestionTransition,
  applyStoryTransition,
  type TransitionState,
} from '@/app/workspace/content-actions'

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

const TEXTAREA =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm ' +
  'text-slate-900 focus-visible:outline focus-visible:outline-2 ' +
  'focus-visible:outline-offset-2 focus-visible:outline-sky-600 ' +
  'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

interface ActionShape {
  name: string
  label: string
  hint: string
  requiresReason: boolean
  destructive?: boolean
}

/**
 * One transition form for stories and questions alike.
 *
 * `kind` picks which server action runs. The two workflows differ in their
 * stages but not in what this form has to do: collect an optional or required
 * piece of writing, send it, and report back what the server said.
 */
export function ContentTransitionForm({
  kind,
  entityId,
  action,
  organisationId,
}: {
  kind: 'story' | 'question'
  entityId: string
  action: ActionShape
  organisationId?: string
}) {
  const [state, submit, pending] = useActionState<TransitionState, FormData>(
    kind === 'story' ? applyStoryTransition : applyQuestionTransition,
    {},
  )

  const fieldId = `${kind}-${action.name}-reason`
  const isAnswer = action.name === 'respond'

  return (
    <form
      action={submit}
      className="space-y-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800"
    >
      <input type="hidden" name={`${kind}_id`} value={entityId} />
      <input type="hidden" name="action" value={action.name} />
      {organisationId ? (
        <input type="hidden" name="organisation_id" value={organisationId} />
      ) : null}

      <div>
        <h3 className="font-medium text-slate-900 dark:text-slate-50">{action.label}</h3>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{action.hint}</p>
      </div>

      {action.name !== 'triage' && action.name !== 'publish' && action.name !== 'submit' ? (
        <div className="space-y-1">
          <label
            htmlFor={fieldId}
            className="block text-sm font-medium text-slate-800 dark:text-slate-200"
          >
            {isAnswer ? 'Answer' : action.requiresReason ? 'Reason' : 'Comments'}
            <span className="font-normal text-slate-600 dark:text-slate-400">
              {action.requiresReason ? ' (required)' : ' (optional)'}
            </span>
          </label>
          <textarea
            id={fieldId}
            name="reason"
            rows={isAnswer ? 6 : 3}
            required={action.requiresReason}
            className={TEXTAREA}
          />
        </div>
      ) : null}

      {action.name === 'reject' ? (
        <label className="flex items-center gap-2 text-sm text-slate-800 dark:text-slate-200">
          <input type="checkbox" name="changes_requested" className="h-4 w-4" />
          Changes requested rather than refused outright
        </label>
      ) : null}

      {state.error ? (
        <p
          role="alert"
          className="rounded-md bg-rose-50 p-3 text-sm text-rose-900 dark:bg-rose-950 dark:text-rose-100"
        >
          {state.error}
        </p>
      ) : null}

      {state.done ? (
        <p
          role="status"
          className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100"
        >
          {state.done}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={pending}
        className={action.destructive ? DESTRUCTIVE : PRIMARY}
      >
        {pending ? 'Working…' : action.label}
      </button>
    </form>
  )
}
