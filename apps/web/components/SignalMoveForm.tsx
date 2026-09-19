'use client'

import { useActionState } from 'react'

import type { TransitionState } from '@/app/workspace/content-actions'
import { applySignalMove } from '@/app/workspace/integrity-actions'
import { FINDINGS, type SignalOffer } from '@/lib/integrity'

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

const FIELD =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600 ' +
  'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

const LABEL = 'block text-xs font-medium text-slate-600 dark:text-slate-400'

/**
 * One move on an integrity signal.
 *
 * The refusals that matter most cannot be checked here and are not guessed
 * at: a finding that cites no approved evidence, and an approver trying to
 * publish their own sign-off, are both refused by the server, and its wording
 * is what the reader sees.
 */
export function SignalMoveForm({
  signalId,
  offer,
  evidenceOptions,
}: {
  signalId: string
  offer: SignalOffer
  /** Approved evidence a finding may cite. */
  evidenceOptions: { id: string; label: string }[]
}) {
  const [state, submit, pending] = useActionState<TransitionState, FormData>(applySignalMove, {})

  return (
    <form
      action={submit}
      className="space-y-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800"
    >
      <input type="hidden" name="signal_id" value={signalId} />
      <input type="hidden" name="move" value={offer.name} />

      <div>
        <h3 className="font-medium text-slate-900 dark:text-slate-50">{offer.label}</h3>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{offer.hint}</p>
      </div>

      {offer.needsFinding ? (
        <div className="space-y-1">
          <label className={LABEL} htmlFor={`${offer.name}-finding`}>
            What the claim turned out to be
          </label>
          <select id={`${offer.name}-finding`} name="finding" required className={FIELD}>
            {FINDINGS.map((finding) => (
              <option key={finding} value={finding}>
                {finding.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {offer.offersEvidence ? (
        <div className="space-y-1">
          <label className={LABEL} htmlFor={`${offer.name}-evidence`}>
            The evidence it rests on
          </label>
          <select id={`${offer.name}-evidence`} name="evidence_id" className={FIELD}>
            <option value="">None cited</option>
            {evidenceOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Only approved evidence is listed, because that is the only kind sign-off
            accepts. &ldquo;Unresolved&rdquo; is the one finding exempt: it asserts nothing
            to source.
          </p>
        </div>
      ) : null}

      {offer.field ? (
        <div className="space-y-1">
          <label className={LABEL} htmlFor={`${offer.name}-${offer.field.name}`}>
            {offer.field.label}
          </label>
          <textarea
            id={`${offer.name}-${offer.field.name}`}
            name={offer.field.name}
            rows={offer.field.rows}
            className={FIELD}
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
