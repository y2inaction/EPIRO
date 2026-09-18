import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'

import { ContentTransitionForm } from '@/components/ContentTransitionForm'
import { Notice } from '@/components/Shell'
import { formatDate, isoDate } from '@/lib/format'
import { roleIn } from '@/lib/session'
import { questionActions, questionWaitingFor } from '@/lib/transitions'
import { getCurrentUser, getQuestion, listQuestionApprovals } from '@/lib/workspace'

export const metadata: Metadata = { title: 'Question' }

const DECISION_LABEL: Record<string, string> = {
  approved: 'Approved',
  rejected: 'Sent back',
  changes_requested: 'Changes requested',
}

export default async function WorkspaceQuestionPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const result = await getQuestion(id)
  if (!result.ok && result.status === 404) {
    notFound()
  }
  if (!result.ok) {
    if (result.status === 401) {
      redirect('/sign-in')
    }
    return <Notice title="This question could not be loaded" detail={result.message} />
  }

  const question = result.value

  // An unclaimed question belongs to no organisation, so there is no role to
  // read against it. Claiming happens on behalf of one of the caller's own
  // organisations, and the server checks their role there. Once it is claimed,
  // the role that matters is the one held in the organisation that claimed it.
  const claimingOrganisation = me.value.memberships[0]
  const role = question.organisation_id
    ? roleIn(me.value, question.organisation_id)
    : claimingOrganisation?.role

  const actions = questionActions(question, role)
  const trail = await listQuestionApprovals(id)

  return (
    <div className="mx-auto max-w-3xl">
      <nav aria-label="Breadcrumb" className="mb-6">
        <Link
          href="/workspace/questions"
          className="rounded-sm text-sm text-slate-600 underline underline-offset-4 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:text-slate-400 dark:hover:text-slate-100"
        >
          ← All questions
        </Link>
      </nav>

      <header className="space-y-3">
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {question.status.replace(/_/g, ' ')} · {question.language}
          {question.category ? ` · ${question.category}` : ''}
        </p>
        <h1 className="text-2xl font-bold leading-snug tracking-tight text-slate-900 dark:text-slate-50">
          {question.question_text}
        </h1>
        <p className="text-sm text-slate-700 dark:text-slate-300">
          {questionWaitingFor(question)}
        </p>
        {/* The submitter is never named here, whatever they chose when they
            asked: is_anonymous governs contact, not publication or display. */}
        {question.location_state || question.location_lga ? (
          <p className="text-sm text-slate-600 dark:text-slate-400">
            About {[question.location_lga, question.location_state].filter(Boolean).join(', ')}
          </p>
        ) : null}
      </header>

      <section aria-labelledby="answer" className="mt-8">
        <h2
          id="answer"
          className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-50"
        >
          The answer
        </h2>
        {question.response ? (
          <>
            <p className="mt-3 leading-relaxed text-slate-800 dark:text-slate-200">
              {question.response}
            </p>
            {question.response_date ? (
              <p className="mt-2 text-xs text-slate-600 dark:text-slate-400">
                Drafted{' '}
                <time dateTime={isoDate(question.response_date)}>
                  {formatDate(question.response_date)}
                </time>
              </p>
            ) : null}
          </>
        ) : (
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
            Nobody has drafted an answer yet.
          </p>
        )}
      </section>

      <section aria-labelledby="trail" className="mt-10">
        <h2
          id="trail"
          className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-50"
        >
          Approval trail
        </h2>

        {!trail.ok ? (
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">{trail.message}</p>
        ) : trail.value.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
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
                  <time
                    dateTime={isoDate(record.decided_at)}
                    className="text-xs text-slate-600 dark:text-slate-400"
                  >
                    {formatDate(record.decided_at)}
                  </time>
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
            Nothing here is yours to move right now. {questionWaitingFor(question)}
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {actions.map((action) => (
              <ContentTransitionForm
                key={action.name}
                kind="question"
                entityId={question.id}
                action={action}
                organisationId={
                  action.name === 'triage' ? claimingOrganisation?.organisation_id : undefined
                }
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
