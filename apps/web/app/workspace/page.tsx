import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { signOut } from '@/app/sign-in/actions'
import { Notice, PageHeading } from '@/components/Shell'
import { formatDate, isoDate } from '@/lib/format'
import { roleIn } from '@/lib/session'
import { waitingFor } from '@/lib/transitions'
import { getCurrentUser, listEvidence, type Evidence } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Workspace',
}

const STATUS_TONE: Record<string, string> = {
  published: 'bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100',
  approved: 'bg-sky-50 text-sky-900 dark:bg-sky-950 dark:text-sky-100',
  verified: 'bg-sky-50 text-sky-900 dark:bg-sky-950 dark:text-sky-100',
  rejected: 'bg-rose-50 text-rose-900 dark:bg-rose-950 dark:text-rose-100',
  archived: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
}

function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ' +
        (STATUS_TONE[status] ?? 'bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-100')
      }
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function EvidenceRow({ record }: { record: Evidence }) {
  const recorded = formatDate(record.evidence_date)

  return (
    <li className="border-b border-slate-200 py-4 last:border-0 dark:border-slate-800">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Link
          href={`/workspace/evidence/${record.id}`}
          className={
            'rounded-sm font-medium text-slate-900 underline-offset-4 hover:underline ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 dark:text-slate-50'
          }
        >
          {record.title}
        </Link>
        <StatusPill status={record.status} />
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-600 dark:text-slate-400">
        <span className="font-mono">{record.reference}</span>
        {recorded ? (
          <>
            <span aria-hidden="true">·</span>
            <time dateTime={isoDate(record.evidence_date)}>{recorded}</time>
          </>
        ) : null}
        <span aria-hidden="true">·</span>
        <span>v{record.version}</span>
      </div>

      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{waitingFor(record)}</p>
    </li>
  )
}

export default async function WorkspacePage({
  searchParams,
}: {
  searchParams: Promise<{ org?: string }>
}) {
  const me = await getCurrentUser()
  if (!me.ok) {
    // Any failure to identify the caller ends the session rather than showing
    // a half-working workspace.
    redirect('/sign-in')
  }

  const user = me.value
  const { org } = await searchParams

  if (user.memberships.length === 0) {
    return (
      <>
        <PageHeading title={`Welcome, ${user.first_name}`} />
        <Notice
          title="You do not belong to an organisation yet"
          detail="An administrator has to add you to one before you can record or review anything."
        />
      </>
    )
  }

  const selected =
    user.memberships.find((m) => m.organisation_id === org) ?? user.memberships[0]
  const role = roleIn(user, selected.organisation_id)
  const result = await listEvidence(selected.organisation_id)

  return (
    <>
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
            {selected.name}
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            Signed in as {user.first_name} {user.last_name} · your role here is{' '}
            <span className="font-medium">{role?.replace(/_/g, ' ')}</span>
          </p>
        </div>

        <form action={signOut}>
          <button
            type="submit"
            className={
              'rounded-md border border-slate-300 px-3 py-2 text-sm font-medium ' +
              'text-slate-700 transition hover:bg-slate-100 ' +
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
              'focus-visible:outline-sky-600 ' +
              'dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800'
            }
          >
            Sign out
          </button>
        </form>
      </div>

      {user.memberships.length > 1 ? (
        <nav aria-label="Organisation" className="mb-8 flex flex-wrap gap-2">
          {user.memberships.map((membership) => (
            <Link
              key={membership.organisation_id}
              href={{ pathname: '/workspace', query: { org: membership.organisation_id } }}
              aria-current={
                membership.organisation_id === selected.organisation_id ? 'true' : undefined
              }
              className={
                'rounded-md border px-3 py-1.5 text-sm transition ' +
                'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
                'focus-visible:outline-sky-600 ' +
                (membership.organisation_id === selected.organisation_id
                  ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                  : 'border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800')
              }
            >
              {membership.name}
            </Link>
          ))}
        </nav>
      ) : null}

      <nav aria-label="Workspace" className="mb-8 flex flex-wrap gap-2">
        <Link
          href="/workspace/stories"
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 transition hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Stories
        </Link>
        <Link
          href="/workspace/questions"
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 transition hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Questions
        </Link>
        <Link
          href="/workspace/intelligence"
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 transition hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Intelligence
        </Link>
      </nav>

      <h2 className="mb-4 text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
        Evidence
      </h2>

      {!result.ok ? (
        <Notice title="Evidence could not be loaded" detail={result.message} />
      ) : result.value.data.length === 0 ? (
        <Notice
          title="No evidence recorded yet"
          detail="Records appear here as they are added."
        />
      ) : (
        <ul className="rounded-xl border border-slate-200 px-5 dark:border-slate-800">
          {result.value.data.map((record) => (
            <EvidenceRow key={record.id} record={record} />
          ))}
        </ul>
      )}
    </>
  )
}
