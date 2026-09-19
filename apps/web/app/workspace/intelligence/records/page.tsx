import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { Notice, PageHeading, Pagination } from '@/components/Shell'
import { formatCount, formatDate, isoDate } from '@/lib/format'
import {
  basisSentence,
  describeRecord,
  measureLabel,
  recordsQuery,
  suppressesSmallBuckets,
  type MeasureCatalogue,
  type RecordSummary,
} from '@/lib/intelligence'
import { getCurrentUser, getRecords, listMeasures } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Records behind a figure',
}

const LINK =
  'rounded-sm underline-offset-4 hover:underline ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600'

/**
 * The records behind a figure.
 *
 * This route is what makes the dashboard explainable rather than asserted. It
 * takes a figure's own basis — the measure and the filters that produced it —
 * and shows the rows that basis resolves to. A number and the records it
 * counted are the same query asked twice.
 *
 * Nothing is suppressed here, and that is deliberate. Suppression stops an
 * aggregate from describing an individual to somebody who could not otherwise
 * see them; it is not a second lock over records their own custodians can
 * already open. A drill-down is scoped exactly as the figure was, so it can
 * never reach further than the number it explains.
 */
export default async function RecordsPage({
  searchParams,
}: {
  searchParams: Promise<{
    measure?: string
    dimension?: string
    value?: string
    geography_id?: string
    page?: string
  }>
}) {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const params = await searchParams
  const measure = params.measure

  if (!measure) {
    return (
      <>
        <PageHeading title="Records behind a figure" />
        <Notice
          title="No figure was named"
          detail="Open this from a number on the dashboard, so it knows what to explain."
        />
        <BackLink />
      </>
    )
  }

  const basis = {
    measure,
    dimension: params.dimension,
    value: params.value,
    geography_id: params.geography_id,
  }
  const page = Math.max(1, Number.parseInt(params.page ?? '1', 10) || 1)

  const [result, catalogue] = await Promise.all([getRecords(basis, page), listMeasures()])
  const measures: MeasureCatalogue | null = catalogue.ok ? catalogue.value : null
  const label = measureLabel(measures, measure)

  if (!result.ok) {
    return (
      <>
        <PageHeading title="Records behind a figure" />
        {/* The API's own refusal, which names the measure or dimension that
            does not exist and what would have worked instead. */}
        <Notice title="These records could not be loaded" detail={result.message} />
        <BackLink />
      </>
    )
  }

  const records = result.value

  return (
    <>
      <PageHeading
        title={basisSentence(records.basis, label)}
        description={`${formatCount(records.total)} ${
          records.total === 1 ? 'record' : 'records'
        }. This is the figure's own basis resolved back to the rows it counted.`}
      />

      {suppressesSmallBuckets(measures, measure) ? (
        <p className="mb-8 max-w-2xl rounded-xl border border-slate-200 p-4 text-sm text-slate-600 dark:border-slate-800 dark:text-slate-400">
          A summary of these records withholds buckets too small to publish. The records
          themselves are not withheld from you: they belong to an organisation you are a
          member of, and the threshold protects the shape of a published summary rather
          than the records from their own custodians.
        </p>
      ) : null}

      {records.data.length === 0 ? (
        <Notice
          title="Nothing matched this basis"
          detail="The figure that led here counted zero records."
        />
      ) : (
        <ul className="rounded-xl border border-slate-200 px-5 dark:border-slate-800">
          {records.data.map((row, index) => (
            <RecordRow
              key={typeof row.id === 'string' ? row.id : index}
              summary={describeRecord(measure, row)}
              createdAt={typeof row.created_at === 'string' ? row.created_at : null}
            />
          ))}
        </ul>
      )}

      {/* Section 81: an unlinked row is a gap, not a bug, and says so. */}
      {records.data.length > 0 && describeRecord(measure, records.data[0]).route === null ? (
        <p className="mt-4 text-xs text-slate-600 dark:text-slate-400">
          There is no workspace screen for {label.toLowerCase()} yet, so these rows do not
          open anywhere. The records exist and the API serves them.
        </p>
      ) : null}

      <Pagination
        page={records.page}
        totalPages={records.total_pages}
        basePath="/workspace/intelligence/records"
        query={recordsQuery(records.basis)}
      />

      <BackLink />
    </>
  )
}

function RecordRow({
  summary,
  createdAt,
}: {
  summary: RecordSummary
  createdAt: string | null
}) {
  const recorded = formatDate(createdAt)

  return (
    <li className="border-b border-slate-200 py-4 last:border-0 dark:border-slate-800">
      {/* Built inline per route rather than from a string, so a destination
          that does not exist is a type error here and not a 404 in somebody's
          browser. */}
      {summary.route === 'evidence' ? (
        <Link
          href={`/workspace/evidence/${summary.id}`}
          className={`${LINK} font-medium text-slate-900 dark:text-slate-50`}
        >
          {summary.title}
        </Link>
      ) : summary.route === 'questions' ? (
        <Link
          href={`/workspace/questions/${summary.id}`}
          className={`${LINK} font-medium text-slate-900 dark:text-slate-50`}
        >
          {summary.title}
        </Link>
      ) : (
        <p className="font-medium text-slate-900 dark:text-slate-50">{summary.title}</p>
      )}

      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-600 dark:text-slate-400">
        {summary.meta.map((fact) => (
          <span key={fact} className="after:ml-2 after:content-['·'] last:after:content-['']">
            {fact}
          </span>
        ))}
        {recorded ? <time dateTime={isoDate(createdAt)}>{recorded}</time> : null}
      </div>
    </li>
  )
}

function BackLink() {
  return (
    <p className="mt-8">
      <Link
        href="/workspace/intelligence"
        className={`${LINK} text-sm text-slate-700 dark:text-slate-300`}
      >
        ← Back to intelligence
      </Link>
    </p>
  )
}
