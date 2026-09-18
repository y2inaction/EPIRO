import type { Metadata } from 'next'

import { CorrectionCard } from '@/components/Cards'
import { Notice, PageHeading, Pagination } from '@/components/Shell'
import { listCorrections } from '@/lib/api'

export const metadata: Metadata = {
  title: 'Corrections',
  description:
    'Claims that were circulating publicly, what was found out about them, and the evidence each finding rests on.',
}

export default async function CorrectionsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>
}) {
  const { page: rawPage } = await searchParams
  const page = Math.max(1, Number.parseInt(rawPage ?? '1', 10) || 1)

  const result = await listCorrections({ page, pageSize: 10 })

  return (
    <>
      <PageHeading
        title="Corrections"
        description="Claims that were circulating publicly, and what was found out about them."
      />

      <p className="mb-8 max-w-2xl rounded-lg bg-slate-100 p-4 text-sm leading-relaxed text-slate-700 dark:bg-slate-900 dark:text-slate-300">
        Every finding here was checked against a recorded piece of evidence and
        approved by someone other than the person who wrote it. Each one links
        to that evidence, so you can check the correction rather than take it on
        trust. Nobody who repeated a claim is named or counted: these records
        are about information, not about people.
      </p>

      {!result.ok ? (
        <Notice title="Corrections are temporarily unavailable" detail={result.message} />
      ) : result.value.data.length === 0 ? (
        <Notice
          title="No corrections have been published yet"
          detail="A finding appears here once it has been approved and released."
        />
      ) : (
        <>
          <div className="space-y-4">
            {result.value.data.map((correction) => (
              <CorrectionCard key={correction.id} correction={correction} />
            ))}
          </div>
          <Pagination
            page={result.value.page}
            totalPages={result.value.total_pages}
            basePath="/corrections"
          />
        </>
      )}
    </>
  )
}
