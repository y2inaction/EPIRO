import type { Metadata } from 'next'

import { EvidenceCard, QuestionCard, StoryCard } from '@/components/Cards'
import { CardGrid, Notice, PageHeading } from '@/components/Shell'
import { search } from '@/lib/api'

export const metadata: Metadata = {
  title: 'Search',
  description: 'Search published stories, evidence records and answers.',
}

function SearchForm({ term }: { term: string }) {
  return (
    // A plain GET form: search works without JavaScript, the result is a real
    // URL a reader can bookmark or send to someone, and the back button does
    // what they expect.
    <form action="/search" method="get" role="search" className="mb-10 flex flex-wrap gap-3">
      <label htmlFor="q" className="sr-only">
        Search published information
      </label>
      <input
        id="q"
        name="q"
        type="search"
        defaultValue={term}
        placeholder="Search stories, evidence and answers"
        className={
          'min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-4 py-2 ' +
          'text-slate-900 placeholder:text-slate-500 ' +
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
          'focus-visible:outline-sky-600 ' +
          'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500'
        }
      />
      <button
        type="submit"
        className={
          'rounded-md bg-slate-900 px-5 py-2 font-medium text-white transition ' +
          'hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 ' +
          'focus-visible:outline-offset-2 focus-visible:outline-sky-600 ' +
          'dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white'
        }
      >
        Search
      </button>
    </form>
  )
}

function Group({
  heading,
  count,
  children,
}: {
  heading: string
  count: number
  children: React.ReactNode
}) {
  if (count === 0) {
    return null
  }

  const id = heading.toLowerCase().replace(/\s+/g, '-')

  return (
    <section aria-labelledby={id} className="space-y-4">
      <h2
        id={id}
        className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50"
      >
        {heading}{' '}
        <span className="text-base font-normal text-slate-600 dark:text-slate-400">
          ({count})
        </span>
      </h2>
      {children}
    </section>
  )
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>
}) {
  const { q } = await searchParams
  const term = (q ?? '').trim()

  if (!term) {
    return (
      <>
        <PageHeading
          title="Search"
          description="Search everything that has been published: stories, evidence records and answers to public questions."
        />
        <SearchForm term="" />
        <Notice
          title="Enter a term to search"
          detail="Partial words match, so “boreh” will find “borehole”."
        />
      </>
    )
  }

  const result = await search(term)

  return (
    <>
      <PageHeading title="Search" />
      <SearchForm term={term} />

      {!result.ok ? (
        <Notice title="Search is temporarily unavailable" detail={result.message} />
      ) : result.value.total === 0 ? (
        <Notice
          title={`Nothing published matches “${term}”`}
          detail="Only published information is searchable here."
        />
      ) : (
        <div className="space-y-12">
          <p className="text-sm text-slate-600 dark:text-slate-400" role="status">
            {result.value.total} result{result.value.total === 1 ? '' : 's'} for “{term}”
          </p>

          <Group heading="Stories" count={result.value.stories.length}>
            <CardGrid>
              {result.value.stories.map((story) => (
                <StoryCard key={story.id} story={story} />
              ))}
            </CardGrid>
          </Group>

          <Group heading="Evidence" count={result.value.evidence.length}>
            <CardGrid>
              {result.value.evidence.map((record) => (
                <EvidenceCard key={record.id} record={record} />
              ))}
            </CardGrid>
          </Group>

          <Group heading="Answers" count={result.value.questions.length}>
            <div className="space-y-4">
              {result.value.questions.map((question) => (
                <QuestionCard key={question.id} question={question} />
              ))}
            </div>
          </Group>
        </div>
      )}
    </>
  )
}
