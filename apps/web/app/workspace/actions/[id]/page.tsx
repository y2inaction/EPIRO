import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'

import { DecisionForm } from '@/components/DecisionForm'
import { PageHeading } from '@/components/Shell'
import { offersFor, waitingFor } from '@/lib/decisions'
import { formatDate, isoDate } from '@/lib/format'
import { getAction, getCurrentUser } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Decision',
}

/**
 * One decision, what prompted it, and what may be done to it now.
 *
 * The screen offers exactly the moves the lifecycle allows from here, and
 * says what the action is waiting for when it offers none — "no buttons"
 * and "finished" are different facts and must not look the same.
 */
export default async function DecisionPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const { id } = await params
  const result = await getAction(id)

  if (!result.ok) {
    if (result.status === 404) {
      notFound()
    }
    return (
      <>
        <PageHeading title="Decision" />
        <p className="text-sm text-slate-600 dark:text-slate-400">{result.message}</p>
      </>
    )
  }

  const action = result.value
  const offers = offersFor(action.status)
  const due = formatDate(action.due_date)

  return (
    <>
      <PageHeading title={action.title} />

      <dl className="mb-8 grid gap-4 sm:grid-cols-2">
        <Fact term="State">
          {action.status.replace(/_/g, ' ')}
          {action.overdue ? ' · overdue' : ''}
        </Fact>
        <Fact term="Raised from">{action.origin_type.replace(/_/g, ' ')}</Fact>
        {due ? (
          <Fact term="Due">
            <time dateTime={isoDate(action.due_date)}>{due}</time>
          </Fact>
        ) : null}
        {action.closed_at ? (
          <Fact term="Closed">
            <time dateTime={isoDate(action.closed_at)}>{formatDate(action.closed_at)}</time>
          </Fact>
        ) : null}
      </dl>

      <section className="mb-8">
        <h2 className="mb-2 text-lg font-semibold text-slate-900 dark:text-slate-50">
          Why this was decided
        </h2>
        <p className="max-w-2xl whitespace-pre-line text-slate-700 dark:text-slate-300">
          {action.rationale}
        </p>
      </section>

      {action.outcome ? (
        <section className="mb-8">
          <h2 className="mb-2 text-lg font-semibold text-slate-900 dark:text-slate-50">
            What happened
          </h2>
          <p className="max-w-2xl whitespace-pre-line text-slate-700 dark:text-slate-300">
            {action.outcome}
          </p>
        </section>
      ) : null}

      <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-slate-50">
        What can happen next
      </h2>

      {offers.length === 0 ? (
        <p className="max-w-2xl text-sm text-slate-600 dark:text-slate-400">
          {waitingFor(action.status, action.overdue)}
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {offers.map((offer) => (
            <DecisionForm key={offer.name} actionId={action.id} offer={offer} />
          ))}
        </div>
      )}

      <p className="mt-8">
        <Link
          href="/workspace/actions"
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

function Fact({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-600 dark:text-slate-400">{term}</dt>
      <dd className="mt-0.5 text-slate-900 dark:text-slate-100">{children}</dd>
    </div>
  )
}
