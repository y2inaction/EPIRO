import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { Notice, PageHeading } from '@/components/Shell'
import { formatDate, isoDate } from '@/lib/format'
import { storyWaitingFor } from '@/lib/transitions'
import { getCurrentUser, listStories } from '@/lib/workspace'

export const metadata: Metadata = { title: 'Stories' }

export default async function WorkspaceStoriesPage() {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const result = await listStories()

  return (
    <>
      <PageHeading
        title="Stories"
        description="Public information built from evidence. A story is signed off by one person and released by another."
      />

      {!result.ok ? (
        <Notice title="Stories could not be loaded" detail={result.message} />
      ) : result.value.data.length === 0 ? (
        <Notice
          title="No stories yet"
          detail="Stories are created from an evidence record."
        />
      ) : (
        <ul className="rounded-xl border border-slate-200 px-5 dark:border-slate-800">
          {result.value.data.map((story) => (
            <li
              key={story.id}
              className="border-b border-slate-200 py-4 last:border-0 dark:border-slate-800"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <Link
                  href={`/workspace/stories/${story.id}`}
                  className="rounded-sm font-medium text-slate-900 underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:text-slate-50"
                >
                  {story.title}
                </Link>
                <span className="text-xs text-slate-600 dark:text-slate-400">
                  {story.status.replace(/_/g, ' ')} · v{story.version}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                {storyWaitingFor(story)}
              </p>
              {story.published_date ? (
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                  Published{' '}
                  <time dateTime={isoDate(story.published_date)}>
                    {formatDate(story.published_date)}
                  </time>
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
