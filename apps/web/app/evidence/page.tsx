import type { Metadata } from 'next'

import { EvidenceCard } from '@/components/Cards'
import { CardGrid, Notice, PageHeading, Pagination } from '@/components/Shell'
import { listEvidence } from '@/lib/api'

export const metadata: Metadata = {
  title: 'Evidence register',
  description:
    'Every published record, with the state of its verification and a permanent reference.',
}

export default async function EvidencePage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>
}) {
  const { page: rawPage } = await searchParams
  const page = Math.max(1, Number.parseInt(rawPage ?? '1', 10) || 1)

  const result = await listEvidence({ page })

  return (
    <>
      <PageHeading
        title="Evidence register"
        description="Each record keeps the reference it is cited by for its whole life, so a claim made about it today can still be checked years from now."
      />

      <p className="mb-8 max-w-2xl rounded-lg bg-slate-100 p-4 text-sm leading-relaxed text-slate-700 dark:bg-slate-900 dark:text-slate-300">
        A verification state describes how far review has got and what it found.
        None of them is a claim that a record is true — that judgement stays with
        you.
      </p>

      {!result.ok ? (
        <Notice title="The register is temporarily unavailable" detail={result.message} />
      ) : result.value.data.length === 0 ? (
        <Notice
          title="No records have been published yet"
          detail="A record appears here once it has been verified, approved and released."
        />
      ) : (
        <>
          <CardGrid>
            {result.value.data.map((record) => (
              <EvidenceCard key={record.id} record={record} />
            ))}
          </CardGrid>
          <Pagination
            page={result.value.page}
            totalPages={result.value.total_pages}
            basePath="/evidence"
          />
        </>
      )}
    </>
  )
}
