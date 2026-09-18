import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'

import { Notice } from '@/components/Shell'
import { TransitionForm } from '@/components/TransitionForm'
import { VerificationBadge } from '@/components/VerificationBadge'
import { formatCount, formatDate, isoDate } from '@/lib/format'
import { roleIn } from '@/lib/session'
import { availableActions, waitingFor } from '@/lib/transitions'
import { getCurrentUser, getEvidence, listApprovals } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Evidence record',
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-slate-200 py-3 dark:border-slate-800">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
        {label}
      </dt>
      <dd className="mt-1 text-slate-800 dark:text-slate-200">{children}</dd>
    </div>
  )
}

const DECISION_LABEL: Record<string, string> = {
  approved: 'Approved',
  rejected: 'Rejected',
  changes_requested: 'Changes requested',
}

export default async function WorkspaceEvidencePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const result = await getEvidence(id)
  if (!result.ok && result.status === 404) {
    // The API reports another tenant's record as missing, and so does this
    // page: it must not confirm that an id exists elsewhere.
    notFound()
  }
  if (!result.ok) {
    if (result.status === 401) {
      redirect('/sign-in')
    }
    return <Notice title="This record could not be loaded" detail={result.message} />
  }

  const evidence = result.value
  const role = roleIn(me.value, evidence.organisation_id)
  const actions = availableActions(evidence, { id: me.value.id, role })
  const trail = await listApprovals(id)
  const recorded = formatDate(evidence.evidence_date)
  const beneficiaries = formatCount(evidence.beneficiaries)

  return (
    <div className="mx-auto max-w-3xl">
      <nav aria-label="Breadcrumb" className="mb-6">
        <Link
          href="/workspace"
          className="rounded-sm text-sm text-slate-600 underline underline-offset-4 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:text-slate-400 dark:hover:text-slate-100"
        >
          ← Workspace
        </Link>
      </nav>

      <header className="space-y-3">
        <p className="font-mono text-sm text-slate-600 dark:text-slate-400">
          {evidence.reference} · version {evidence.version}
        </p>
        <h1 className="text-3xl font-bold leading-tight tracking-tight text-slate-900 dark:text-slate-50">
          {evidence.title}
        </h1>
        <VerificationBadge status={evidence.verification_status} withMeaning />
        <p className="text-sm text-slate-700 dark:text-slate-300">{waitingFor(evidence)}</p>
      </header>

      {evidence.description ? (
        <p className="mt-6 leading-relaxed text-slate-800 dark:text-slate-200">
          {evidence.description}
        </p>
      ) : null}

      <dl className="mt-6">
        <Field label="Status">{evidence.status.replace(/_/g, ' ')}</Field>
        {recorded ? (
          <Field label="Date of the evidence">
            <time dateTime={isoDate(evidence.evidence_date)}>{recorded}</time>
          </Field>
        ) : null}
        {evidence.outcome ? <Field label="Outcome">{evidence.outcome}</Field> : null}
        {beneficiaries ? <Field label="People reached">{beneficiaries}</Field> : null}
      </dl>

      <section aria-labelledby="trail" className="mt-10">
        <h2
          id="trail"
          className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-50"
        >
          Approval trail
        </h2>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          Every decision is kept, including the ones that sent this back.
        </p>

        {!trail.ok ? (
          <p className="mt-4 text-sm text-slate-600 dark:text-slate-400">{trail.message}</p>
        ) : trail.value.length === 0 ? (
          <p className="mt-4 text-sm text-slate-600 dark:text-slate-400">
            No decision has been recorded against this yet.
          </p>
        ) : (
          <ol className="mt-4 space-y-3">
            {trail.value.map((record) => (
              <li
                key={record.id}
                className="rounded-lg border border-slate-200 p-4 dark:border-slate-800"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium text-slate-900 dark:text-slate-50">
                    {DECISION_LABEL[record.decision] ?? record.decision}
                  </span>
                  <span className="text-xs text-slate-600 dark:text-slate-400">
                    <time dateTime={isoDate(record.decided_at)}>
                      {formatDate(record.decided_at)}
                    </time>
                    {record.entity_version !== null ? ` · covered version ${record.entity_version}` : ''}
                  </span>
                </div>
                {record.comments ? (
                  <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
                    {record.comments}
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section aria-labelledby="actions" className="mt-10">
        <h2
          id="actions"
          className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-50"
        >
          What you can do
        </h2>

        {actions.length === 0 ? (
          <p className="mt-3 rounded-lg bg-slate-100 p-4 text-sm text-slate-700 dark:bg-slate-900 dark:text-slate-300">
            Nothing here is yours to move right now. {waitingFor(evidence)}
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {actions.map((action) => (
              <TransitionForm key={action.name} evidenceId={evidence.id} action={action} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
