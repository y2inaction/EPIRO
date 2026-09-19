import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'

import { ContentTransitionForm } from '@/components/ContentTransitionForm'
import { Notice } from '@/components/Shell'
import { formatDate, isoDate } from '@/lib/format'
import { roleIn } from '@/lib/session'
import { storyActions, storyWaitingFor } from '@/lib/transitions'
import { getCurrentUser, getStory, listStoryApprovals } from '@/lib/workspace'

export const metadata: Metadata = { title: 'Story' }

const DECISION_LABEL: Record<string, string> = {
  approved: 'Approved',
  rejected: 'Sent back',
  changes_requested: 'Changes requested',
}

export default async function WorkspaceStoryPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const result = await getStory(id)
  if (!result.ok && result.status === 404) {
    notFound()
  }
  if (!result.ok) {
    if (result.status === 401) {
      redirect('/sign-in')
    }
    return <Notice title="This story could not be loaded" detail={result.message} />
  }

  const story = result.value
  const role = roleIn(me.value, story.organisation_id)
  const actions = storyActions(story, role)
  const trail = await listStoryApprovals(id)

  return (
    <div className="mx-auto max-w-3xl">
      <nav aria-label="Breadcrumb" className="mb-6">
        <Link
          href="/workspace/stories"
          className="rounded-sm text-sm text-slate-600 underline underline-offset-4 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:text-slate-400 dark:hover:text-slate-100"
        >
          ← All stories
        </Link>
      </nav>

      <header className="space-y-3">
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {story.status.replace(/_/g, ' ')} · version {story.version} · {story.language}
        </p>
        <h1 className="text-3xl font-bold leading-tight tracking-tight text-slate-900 dark:text-slate-50">
          {story.title}
        </h1>
        {story.headline ? (
          <p className="text-lg text-slate-700 dark:text-slate-300">{story.headline}</p>
        ) : null}
        <p className="text-sm text-slate-700 dark:text-slate-300">{storyWaitingFor(story)}</p>
      </header>

      <section aria-labelledby="copy" className="mt-8">
        <h2 id="copy" className="sr-only">
          The story
        </h2>
        {story.summary ? (
          <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300">
            {story.summary}
          </p>
        ) : null}
        <div className="mt-4 space-y-4 leading-relaxed text-slate-800 dark:text-slate-200">
          {story.body
            .split(/\n{2,}/)
            .map((paragraph) => paragraph.trim())
            .filter(Boolean)
            .map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
        </div>
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
                  <span className="text-xs text-slate-600 dark:text-slate-400">
                    <time dateTime={isoDate(record.decided_at)}>
                      {formatDate(record.decided_at)}
                    </time>
                    {record.entity_version !== null
                      ? ` · covered version ${record.entity_version}`
                      : ''}
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
            Nothing here is yours to move right now. {storyWaitingFor(story)}
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {actions.map((action) => (
              <ContentTransitionForm
                key={action.name}
                kind="story"
                entityId={story.id}
                action={action}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
