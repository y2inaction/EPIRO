import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { Notice, PageHeading } from '@/components/Shell'
import { formatDate, isoDate } from '@/lib/format'
import { listActions, getCurrentUser, type ActionRecord } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Decisions',
}

const TONE: Record<string, string> = {
  done: 'bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100',
  in_progress: 'bg-sky-50 text-sky-900 dark:bg-sky-950 dark:text-sky-100',
  accepted: 'bg-sky-50 text-sky-900 dark:bg-sky-950 dark:text-sky-100',
  dropped: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
}

const VIEWS = [
  { label: 'Everything', query: {} },
  { label: 'Proposed', query: { status: 'proposed' } },
  { label: 'Under way', query: { status: 'in_progress' } },
  { label: 'Overdue', query: { overdue: 'true' } },
  { label: 'Closed', query: { status: 'done' } },
] as const

/**
 * The decision register.
 *
 * What the organisation decided to do about what it knows. Every row traces
 * back to the finding that prompted it, and an action that is past its date
 * says so — overdue is derived by the server on every read, so this screen
 * never shows a stale flag.
 */
export default async function DecisionsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; overdue?: string }>
}) {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const params = await searchParams
  const result = await listActions(params)

  return (
    <>
      <PageHeading
        title="Decisions"
        description="What was decided because of what the organisation knows — who owns it, and how it ended."
      />

      <p className="mb-6">
        <Link
          href="/workspace/actions/new"
          className={
            'rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition ' +
            'hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 ' +
            'focus-visible:outline-offset-2 focus-visible:outline-sky-600 ' +
            'dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white'
          }
        >
          Raise a decision
        </Link>
      </p>

      <nav aria-label="View" className="mb-8 flex flex-wrap gap-2">
        {VIEWS.map((view) => {
          const here =
            (view.query as { status?: string }).status === params.status &&
            (view.query as { overdue?: string }).overdue === params.overdue

          return (
            <Link
              key={view.label}
              href={{ pathname: '/workspace/actions', query: view.query }}
              aria-current={here ? 'page' : undefined}
              className={
                'rounded-md border px-3 py-1.5 text-sm transition ' +
                'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
                'focus-visible:outline-sky-600 ' +
                (here
                  ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                  : 'border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800')
              }
            >
              {view.label}
            </Link>
          )
        })}
      </nav>

      {!result.ok ? (
        <Notice title="The register could not be loaded" detail={result.message} />
      ) : result.value.data.length === 0 ? (
        <Notice
          title="Nothing on the register under this view"
          detail="An action is raised against a finding, a signal, a scenario or an evidence record."
        />
      ) : (
        <ul className="rounded-xl border border-slate-200 px-5 dark:border-slate-800">
          {result.value.data.map((action) => (
            <Row key={action.id} action={action} />
          ))}
        </ul>
      )}

      <p className="mt-8 max-w-2xl text-xs text-slate-600 dark:text-slate-400">
        There is deliberately no way to narrow this by owner. Who owns an action is on the
        action, where it is accountability; a register sliced by person is a report on
        staff.
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

function Row({ action }: { action: ActionRecord }) {
  const due = formatDate(action.due_date)

  return (
    <li className="border-b border-slate-200 py-4 last:border-0 dark:border-slate-800">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Link
          href={`/workspace/actions/${action.id}`}
          className={
            'rounded-sm font-medium text-slate-900 underline-offset-4 hover:underline ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 dark:text-slate-50'
          }
        >
          {action.title}
        </Link>

        <span className="flex items-center gap-2">
          {action.overdue ? (
            <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-100">
              Overdue
            </span>
          ) : null}
          <span
            className={
              'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ' +
              (TONE[action.status] ??
                'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300')
            }
          >
            {action.status.replace(/_/g, ' ')}
          </span>
        </span>
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-600 dark:text-slate-400">
        <span>from {action.origin_type.replace(/_/g, ' ')}</span>
        {due ? (
          <>
            <span aria-hidden="true">·</span>
            <time dateTime={isoDate(action.due_date)}>due {due}</time>
          </>
        ) : null}
      </div>
    </li>
  )
}
