import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { getStory } from '@/lib/api'
import { formatDate, isoDate } from '@/lib/format'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>
}): Promise<Metadata> {
  const { id } = await params
  const result = await getStory(id)

  if (!result.ok) {
    return { title: 'Story' }
  }

  return {
    title: result.value.title,
    description: result.value.summary ?? result.value.headline ?? undefined,
  }
}

export default async function StoryPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const result = await getStory(id)

  // A story that is not published is served as 404 by the API, and the portal
  // renders it the same way: the reader is not told that a draft exists.
  if (!result.ok && result.status === 404) {
    notFound()
  }

  if (!result.ok) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center dark:border-slate-700">
        <p className="font-medium text-slate-800 dark:text-slate-200">
          This story is temporarily unavailable
        </p>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{result.message}</p>
      </div>
    )
  }

  const story = result.value
  const published = formatDate(story.published_date)

  return (
    <article className="mx-auto max-w-2xl">
      <nav aria-label="Breadcrumb" className="mb-6">
        <Link
          href="/stories"
          className="rounded-sm text-sm text-slate-600 underline underline-offset-4 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:text-slate-400 dark:hover:text-slate-100"
        >
          ← All stories
        </Link>
      </nav>

      <header className="space-y-4 border-b border-slate-200 pb-6 dark:border-slate-800">
        <h1 className="text-3xl font-bold leading-tight tracking-tight text-slate-900 dark:text-slate-50">
          {story.title}
        </h1>

        {story.headline ? (
          <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300">
            {story.headline}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-600 dark:text-slate-400">
          {story.organisation ? <span>{story.organisation.name}</span> : null}
          {story.organisation && published ? <span aria-hidden="true">·</span> : null}
          {published ? (
            <time dateTime={isoDate(story.published_date)}>{published}</time>
          ) : null}
        </div>
      </header>

      {story.summary ? (
        <p className="mt-6 text-lg leading-relaxed text-slate-700 dark:text-slate-300">
          {story.summary}
        </p>
      ) : null}

      <div className="mt-6 space-y-4 leading-relaxed text-slate-800 dark:text-slate-200">
        {story.body
          .split(/\n{2,}/)
          .map((paragraph) => paragraph.trim())
          .filter(Boolean)
          .map((paragraph, index) => (
            // Paragraphs have no stable identity of their own; the index is
            // the position, and the list never reorders.
            <p key={index}>{paragraph}</p>
          ))}
      </div>

      {story.evidence_reference ? (
        <aside className="mt-10 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            The evidence behind this story
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
            This story was approved on the basis of one recorded piece of
            evidence. You can read that record, and the state of its
            verification, directly.
          </p>
          <Link
            href={`/evidence/${story.evidence_reference}`}
            className="mt-3 inline-block rounded-md bg-slate-900 px-4 py-2 font-mono text-sm text-white transition hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          >
            {story.evidence_reference}
          </Link>
        </aside>
      ) : null}
    </article>
  )
}
