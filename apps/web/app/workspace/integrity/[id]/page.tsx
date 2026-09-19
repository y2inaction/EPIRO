import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'

import { SignalMoveForm } from '@/components/SignalMoveForm'
import { PageHeading } from '@/components/Shell'
import { formatDate, isoDate } from '@/lib/format'
import { offersFor, waitingFor } from '@/lib/integrity'
import { getCurrentUser, getSignal, listEvidence } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Integrity signal',
}

/** Evidence a finding may cite: the API accepts approved or published only. */
const CITABLE = new Set(['approved', 'published'])

/**
 * One circulating claim, what was found out, and what may happen next.
 *
 * The screen offers the moves the lifecycle allows from here and says what
 * the signal is waiting for when it offers none. Two refusals it does not
 * try to predict — a sign-off with no approved evidence behind it, and an
 * approver publishing their own sign-off — are enforced by the server, and
 * its wording is what a reader sees.
 */
export default async function SignalPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const { id } = await params
  const result = await getSignal(id)

  if (!result.ok) {
    if (result.status === 404) {
      notFound()
    }
    return (
      <>
        <PageHeading title="Integrity signal" />
        <p className="text-sm text-slate-600 dark:text-slate-400">{result.message}</p>
      </>
    )
  }

  const signal = result.value
  const offers = offersFor(signal.status)

  // Only what sign-off will accept is offered, so the citation control cannot
  // lead somebody into a refusal the list could have avoided.
  const evidence = await listEvidence(signal.organisation_id, 1, 100)
  const citable = !evidence.ok
    ? []
    : evidence.value.data
        .filter((record) => CITABLE.has(record.status))
        .map((record) => ({ id: record.id, label: `${record.reference} — ${record.title}` }))

  return (
    <>
      <PageHeading title="Integrity signal" />

      <section className="mb-8">
        <h2 className="mb-2 text-lg font-semibold text-slate-900 dark:text-slate-50">
          The claim
        </h2>
        <p className="max-w-2xl whitespace-pre-line text-slate-700 dark:text-slate-300">
          {signal.claim}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-600 dark:text-slate-400">
          <span>{signal.status.replace(/_/g, ' ')}</span>
          {signal.source ? (
            <>
              <span aria-hidden="true">·</span>
              <span>seen on {signal.source}</span>
            </>
          ) : null}
          {signal.first_observed ? (
            <>
              <span aria-hidden="true">·</span>
              <time dateTime={isoDate(signal.first_observed)}>
                first observed {formatDate(signal.first_observed)}
              </time>
            </>
          ) : null}
        </div>
      </section>

      {signal.assessment ? (
        <section className="mb-8">
          <h2 className="mb-2 text-lg font-semibold text-slate-900 dark:text-slate-50">
            What was found — {signal.finding?.replace(/_/g, ' ')}
          </h2>
          <p className="max-w-2xl whitespace-pre-line text-slate-700 dark:text-slate-300">
            {signal.assessment}
          </p>
          {signal.evidence_id ? (
            <p className="mt-2 text-sm">
              <Link
                href={`/workspace/evidence/${signal.evidence_id}`}
                className={
                  'rounded-sm text-slate-700 underline-offset-4 hover:underline ' +
                  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
                  'focus-visible:outline-sky-600 dark:text-slate-300'
                }
              >
                The evidence this rests on
              </Link>
            </p>
          ) : null}
        </section>
      ) : null}

      {signal.response ? (
        <section className="mb-8">
          <h2 className="mb-2 text-lg font-semibold text-slate-900 dark:text-slate-50">
            What the body said back
          </h2>
          <p className="max-w-2xl whitespace-pre-line text-slate-700 dark:text-slate-300">
            {signal.response}
          </p>
        </section>
      ) : null}

      <h2 className="mb-2 text-lg font-semibold text-slate-900 dark:text-slate-50">
        What can happen next
      </h2>
      <p className="mb-4 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
        {waitingFor(signal)}
      </p>

      {offers.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {offers.map((offer) => (
            <SignalMoveForm
              key={offer.name}
              signalId={signal.id}
              offer={offer}
              evidenceOptions={citable}
            />
          ))}
        </div>
      ) : null}

      <p className="mt-8">
        <Link
          href="/workspace/integrity"
          className={
            'text-sm text-slate-700 underline-offset-4 hover:underline ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 dark:text-slate-300'
          }
        >
          ← Back to the register
        </Link>
      </p>
    </>
  )
}
