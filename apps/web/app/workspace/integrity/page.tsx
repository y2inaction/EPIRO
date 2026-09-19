import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { Notice, PageHeading } from '@/components/Shell'
import { formatDate, isoDate } from '@/lib/format'
import type { Signal } from '@/lib/integrity'
import { getCurrentUser, listSignals } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Integrity',
}

const TONE: Record<string, string> = {
  published: 'bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100',
  approved: 'bg-sky-50 text-sky-900 dark:bg-sky-950 dark:text-sky-100',
  assessed: 'bg-sky-50 text-sky-900 dark:bg-sky-950 dark:text-sky-100',
  withdrawn: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  closed: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
}

/**
 * Claims circulating in public, and what the body found out about them.
 *
 * Every row is about information. There is deliberately nothing here about
 * who is spreading a claim — the table has no column for an account, a handle
 * or an audience, and a test asserts none has appeared. The record is about
 * the claim; the people carrying it are not the platform's business.
 */
export default async function IntegrityPage() {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const result = await listSignals()

  return (
    <>
      <PageHeading
        title="Information integrity"
        description="Claims circulating in public, what the body found out about each one, and what it said back."
      />

      {!result.ok ? (
        <Notice title="The register could not be loaded" detail={result.message} />
      ) : result.value.data.length === 0 ? (
        <Notice
          title="No claims logged"
          detail="A signal is logged by staff. There is deliberately no public submission route."
        />
      ) : (
        <ul className="rounded-xl border border-slate-200 px-5 dark:border-slate-800">
          {result.value.data.map((signal) => (
            <Row key={signal.id} signal={signal} />
          ))}
        </ul>
      )}

      <p className="mt-8 max-w-2xl text-xs text-slate-600 dark:text-slate-400">
        A finding describes the claim, never whoever repeated it. There is no field
        anywhere for an account, a handle or an audience.
      </p>

      <p className="mt-8">
        <Link
          href="/workspace"
          className={
            'text-sm text-slate-700 underline-offset-4 hover:underline ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 dark:text-slate-300'
          }
        >
          ← Back to the workspace
        </Link>
      </p>
    </>
  )
}

function Row({ signal }: { signal: Signal }) {
  const seen = formatDate(signal.first_observed)

  return (
    <li className="border-b border-slate-200 py-4 last:border-0 dark:border-slate-800">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Link
          href={`/workspace/integrity/${signal.id}`}
          className={
            'rounded-sm font-medium text-slate-900 underline-offset-4 hover:underline ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 dark:text-slate-50'
          }
        >
          {signal.claim}
        </Link>

        <span className="flex items-center gap-2">
          {signal.finding ? (
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              {signal.finding.replace(/_/g, ' ')}
            </span>
          ) : null}
          <span
            className={
              'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ' +
              (TONE[signal.status] ??
                'bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-100')
            }
          >
            {signal.status.replace(/_/g, ' ')}
          </span>
        </span>
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-600 dark:text-slate-400">
        {/* The channel it was seen on, never a person. */}
        {signal.source ? <span>Seen on {signal.source}</span> : null}
        {seen ? (
          <>
            {signal.source ? <span aria-hidden="true">·</span> : null}
            <time dateTime={isoDate(signal.first_observed)}>first observed {seen}</time>
          </>
        ) : null}
      </div>
    </li>
  )
}
