import type { Metadata } from 'next'

import { StoryCard } from '@/components/Cards'
import { CardGrid, Notice, PageHeading, Pagination } from '@/components/Shell'
import { listStories } from '@/lib/api'

export const metadata: Metadata = {
  title: 'Stories',
  description: 'Published stories, each linked to the evidence it rests on.',
}

export default async function StoriesPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>
}) {
  const { page: rawPage } = await searchParams
  const page = Math.max(1, Number.parseInt(rawPage ?? '1', 10) || 1)

  const result = await listStories({ page })

  return (
    <>
      <PageHeading
        title="Stories"
        description="What the evidence adds up to. Every story carries the reference of the record behind it, so you can check the claim yourself."
      />

      {!result.ok ? (
        <Notice title="Stories are temporarily unavailable" detail={result.message} />
      ) : result.value.data.length === 0 ? (
        <Notice
          title="No stories have been published yet"
          detail="A story appears here once it has been approved and released."
        />
      ) : (
        <>
          <CardGrid>
            {result.value.data.map((story) => (
              <StoryCard key={story.id} story={story} />
            ))}
          </CardGrid>
          <Pagination
            page={result.value.page}
            totalPages={result.value.total_pages}
            basePath="/stories"
          />
        </>
      )}
    </>
  )
}
