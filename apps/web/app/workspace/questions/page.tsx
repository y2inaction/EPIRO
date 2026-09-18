import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { Notice, PageHeading } from '@/components/Shell'
import { questionWaitingFor } from '@/lib/transitions'
import {
  getCurrentUser,
  listQuestions,
  listUntriagedQuestions,
  type Question,
} from '@/lib/workspace'

export const metadata: Metadata = { title: 'Questions' }

function QuestionRow({ question }: { question: Question }) {
  return (
    <li className="border-b border-slate-200 py-4 last:border-0 dark:border-slate-800">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Link
          href={`/workspace/questions/${question.id}`}
          className="rounded-sm font-medium text-slate-900 underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:text-slate-50"
        >
          {question.question_text}
        </Link>
        <span className="text-xs text-slate-600 dark:text-slate-400">
          {question.status.replace(/_/g, ' ')}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
        {questionWaitingFor(question)}
      </p>
      {question.location_state || question.location_lga ? (
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
          About {[question.location_lga, question.location_state].filter(Boolean).join(', ')}
        </p>
      ) : null}
    </li>
  )
}

export default async function WorkspaceQuestionsPage({
  searchParams,
}: {
  searchParams: Promise<{ org?: string }>
}) {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const { org } = await searchParams
  const selected =
    me.value.memberships.find((m) => m.organisation_id === org) ?? me.value.memberships[0]

  const inbox = await listUntriagedQuestions()
  const mine = selected ? await listQuestions(selected.organisation_id) : null

  return (
    <>
      <PageHeading
        title="Questions"
        description="What the public has asked. An answer is published only after someone other than its author approves it."
      />

      <section aria-labelledby="inbox" className="mb-12">
        <h2
          id="inbox"
          className="mb-1 text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50"
        >
          Unclaimed
        </h2>
        <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
          Submitted by the public and not yet assigned to any body. Claiming one
          makes it your organisation&rsquo;s to answer.
        </p>

        {!inbox.ok ? (
          <Notice title="The inbox could not be loaded" detail={inbox.message} />
        ) : inbox.value.data.length === 0 ? (
          <Notice title="Nothing unclaimed" detail="Every question has been picked up." />
        ) : (
          <ul className="rounded-xl border border-slate-200 px-5 dark:border-slate-800">
            {inbox.value.data.map((question) => (
              <QuestionRow key={question.id} question={question} />
            ))}
          </ul>
        )}
      </section>

      {selected ? (
        <section aria-labelledby="ours">
          <h2
            id="ours"
            className="mb-4 text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50"
          >
            {selected.name}
          </h2>

          {!mine || !mine.ok ? (
            <Notice
              title="Questions could not be loaded"
              detail={mine && !mine.ok ? mine.message : undefined}
            />
          ) : mine.value.data.length === 0 ? (
            <Notice
              title="No questions yet"
              detail="Questions appear here once they are claimed."
            />
          ) : (
            <ul className="rounded-xl border border-slate-200 px-5 dark:border-slate-800">
              {mine.value.data.map((question) => (
                <QuestionRow key={question.id} question={question} />
              ))}
            </ul>
          )}
        </section>
      ) : null}
    </>
  )
}
