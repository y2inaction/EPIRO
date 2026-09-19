import type { Metadata } from 'next'

import { QuestionCard } from '@/components/Cards'
import { Notice, PageHeading, Pagination } from '@/components/Shell'
import { listQuestions } from '@/lib/api'

export const metadata: Metadata = {
  title: 'Questions and answers',
  description:
    'Questions the public asked, with the answers that were checked and approved before publication.',
}

export default async function QuestionsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>
}) {
  const { page: rawPage } = await searchParams
  const page = Math.max(1, Number.parseInt(rawPage ?? '1', 10) || 1)

  const result = await listQuestions({ page, pageSize: 10 })

  return (
    <>
      <PageHeading
        title="Questions and answers"
        description="Questions the public asked. An answer appears here only after someone other than its author approved it."
      />

      <p className="mb-8 max-w-2xl rounded-lg bg-slate-100 p-4 text-sm leading-relaxed text-slate-700 dark:bg-slate-900 dark:text-slate-300">
        The people who asked these questions are never identified here, whatever
        they chose when they submitted them.
      </p>

      {!result.ok ? (
        <Notice title="Answers are temporarily unavailable" detail={result.message} />
      ) : result.value.data.length === 0 ? (
        <Notice
          title="No answers have been published yet"
          detail="A question and its answer appear here once the answer has been approved."
        />
      ) : (
        <>
          <div className="space-y-4">
            {result.value.data.map((question) => (
              <QuestionCard key={question.id} question={question} />
            ))}
          </div>
          <Pagination
            page={result.value.page}
            totalPages={result.value.total_pages}
            basePath="/questions"
          />
        </>
      )}
    </>
  )
}
