import Link from 'next/link'

import { StoryCard } from '@/components/Cards'
import { CardGrid, Notice } from '@/components/Shell'
import { listStories } from '@/lib/api'

const SECTION_LINK =
  'rounded-sm text-sm font-medium text-sky-700 underline underline-offset-4 ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600 dark:text-sky-400'

const ENTRY_CARD =
  'block rounded-xl border border-slate-200 bg-white p-6 transition ' +
  'hover:border-slate-300 hover:shadow-sm ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600 ' +
  'dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700'

const ENTRIES = [
  {
    href: '/evidence',
    title: 'Evidence register',
    description:
      'Every published record, with the state of its verification and a permanent reference you can cite.',
  },
  {
    href: '/stories',
    title: 'Stories',
    description:
      'What the evidence adds up to, written up and linked back to the records behind it.',
  },
  {
    href: '/questions',
    title: 'Questions and answers',
    description:
      'Questions the public asked, and the answers that were checked and approved before publication.',
  },
] as const

export default async function Home() {
  const featured = await listStories({ featuredOnly: true, pageSize: 3 })
  const recent = await listStories({ pageSize: 6 })

  const highlights = featured.ok && featured.value.data.length > 0 ? featured.value : null
  const latest = recent.ok ? recent.value : null

  return (
    <div className="space-y-14">
      <section className="space-y-4">
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
          Evidence you can follow back to its source
        </h1>
        <p className="max-w-2xl text-lg leading-relaxed text-slate-600 dark:text-slate-400">
          Nothing is published here without a recorded source, a check by someone
          other than the person who wrote it, and an approval by someone other
          than the person who checked it. Every claim carries the reference of the
          record it rests on.
        </p>
      </section>

      <section aria-labelledby="explore">
        <h2 id="explore" className="sr-only">
          Explore the portal
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {ENTRIES.map((entry) => (
            <Link key={entry.href} href={entry.href} className={ENTRY_CARD}>
              <span className="block font-semibold text-slate-900 dark:text-slate-50">
                {entry.title}
              </span>
              <span className="mt-2 block text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                {entry.description}
              </span>
            </Link>
          ))}
        </div>
      </section>

      {highlights ? (
        <section aria-labelledby="featured" className="space-y-4">
          <div className="flex items-baseline justify-between gap-4">
            <h2
              id="featured"
              className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50"
            >
              Featured
            </h2>
            <Link href="/stories" className={SECTION_LINK}>
              All stories
            </Link>
          </div>
          <CardGrid>
            {highlights.data.map((story) => (
              <StoryCard key={story.id} story={story} />
            ))}
          </CardGrid>
        </section>
      ) : null}

      <section aria-labelledby="recent" className="space-y-4">
        <div className="flex items-baseline justify-between gap-4">
          <h2
            id="recent"
            className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50"
          >
            Recently published
          </h2>
          <Link href="/stories" className={SECTION_LINK}>
            All stories
          </Link>
        </div>

        {!recent.ok ? (
          <Notice
            title="Information is temporarily unavailable"
            detail={recent.message}
          />
        ) : latest && latest.data.length > 0 ? (
          <CardGrid>
            {latest.data.map((story) => (
              <StoryCard key={story.id} story={story} />
            ))}
          </CardGrid>
        ) : (
          <Notice
            title="Nothing has been published yet"
            detail="Published stories will appear here as they clear approval."
          />
        )}
      </section>
    </div>
  )
}
