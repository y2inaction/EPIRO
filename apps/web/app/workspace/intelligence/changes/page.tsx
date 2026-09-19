import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { FilterBar, FiltersSetAside } from '@/components/FilterBar'
import { IntelligenceNav } from '@/components/IntelligenceNav'
import { Notice, PageHeading, Pagination } from '@/components/Shell'
import { formatCount, formatDate, isoDate } from '@/lib/format'
import {
  actionLabel,
  filtersFor,
  filtersFromParams,
  measureLabel,
  summariseFields,
  unsupportedFilters,
  type ChangeEntry,
  type MeasureCatalogue,
} from '@/lib/intelligence'
import { getChanges, getCurrentUser, listMeasures, listNamed } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Changes',
}

const HERE = '/workspace/intelligence/changes'

const LINK =
  'rounded-sm underline-offset-4 hover:underline ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600'

/**
 * What changed, when, where, on what evidence, and by whom.
 *
 * The questions a dashboard of totals cannot answer. None of this is new
 * data: every state transition already writes an audit entry, because the
 * platform's accountability guarantee depends on it. This reads that trail as
 * intelligence rather than as forensics.
 *
 * **Who acted is named per change and nowhere else.** That is what an audit
 * trail is for — a decision somebody has to answer for. There is deliberately
 * no way to filter or group by the person: the same fact aggregated over
 * people is a productivity report on staff, and the prohibition on profiling
 * is not only about citizens.
 */
export default async function ChangesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const user = me.value
  const params = await searchParams
  const asked = filtersFromParams(params)
  const measure = params.measure ?? 'evidence'
  const action = params.action
  const page = Math.max(1, Number.parseInt(params.page ?? '1', 10) || 1)

  if (user.memberships.length === 0) {
    return (
      <>
        <PageHeading title="Changes" />
        <IntelligenceNav current={HERE} filters={asked} />
        <Notice
          title="There is nothing to show yet"
          detail="This reads the trail of your organisations' records, and you do not belong to one."
        />
      </>
    )
  }

  const catalogue = await listMeasures()
  const measures: MeasureCatalogue | null = catalogue.ok ? catalogue.value : null
  const spec = measures?.measures.find((m) => m.name === measure)

  const supported = spec?.filters ?? []
  const filters = filtersFor(asked, supported)
  const setAside = unsupportedFilters(asked, supported)

  const [feed, areas, themes] = await Promise.all([
    getChanges(measure, filters, action, page),
    supported.includes('geography_id') ? listNamed('geography_id') : [],
    supported.includes('thematic_area_id') ? listNamed('thematic_area_id') : [],
  ])

  return (
    <>
      <PageHeading
        title="Changes"
        description="What changed, when it changed, which record it was about, and who is answerable for it."
      />

      <IntelligenceNav current={HERE} filters={asked} />

      {/* Which trail to read. A separate control from the filters because it
          is not a filter: it decides which records' history is being asked
          about at all. */}
      <nav aria-label="Measure" className="mb-6 flex flex-wrap gap-2">
        {(measures?.measures ?? []).map((option) => (
          <Link
            key={option.name}
            href={{ pathname: HERE, query: { ...filtersFor(asked, option.filters), measure: option.name } }}
            aria-current={option.name === measure ? 'true' : undefined}
            className={
              'rounded-md border px-3 py-1.5 text-sm transition ' +
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
              'focus-visible:outline-sky-600 ' +
              (option.name === measure
                ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                : 'border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800')
            }
          >
            {option.label}
          </Link>
        ))}
      </nav>

      <FilterBar
        action={HERE}
        filters={filters}
        available={supported}
        organisations={user.memberships.map((m) => ({ id: m.organisation_id, name: m.name }))}
        areas={areas}
        themes={themes}
        hidden={{ measure }}
        dateNote={feed.ok ? feed.value.date_note : undefined}
      />

      <FiltersSetAside names={setAside} />

      {!feed.ok ? (
        <Notice title="The trail could not be read" detail={feed.message} />
      ) : (
        <>
          {feed.value.by_action.length > 0 ? (
            <nav aria-label="Kind of change" className="mb-6 flex flex-wrap gap-2">
              <KindLink
                label="Every kind"
                count={feed.value.total}
                query={{ ...filters, measure }}
                current={!action}
              />
              {feed.value.by_action.map((figure) => (
                <KindLink
                  key={figure.label}
                  label={actionLabel(figure.label)}
                  count={figure.value ?? 0}
                  query={{ ...filters, measure, action: figure.label }}
                  current={action === figure.label}
                />
              ))}
            </nav>
          ) : null}

          {feed.value.data.length === 0 ? (
            <Notice
              title="Nothing changed under these filters"
              detail="A record with no recorded transitions has not been acted on since it was created."
            />
          ) : (
            <ul className="rounded-xl border border-slate-200 px-5 dark:border-slate-800">
              {feed.value.data.map((entry) => (
                <ChangeRow key={entry.id} entry={entry} measure={measure} />
              ))}
            </ul>
          )}

          <Pagination
            page={feed.value.page}
            totalPages={feed.value.total_pages}
            basePath={HERE}
            query={{
              ...filters,
              measure,
              ...(action ? { action } : {}),
            }}
          />

          <p className="mt-8 max-w-2xl text-xs text-slate-600 dark:text-slate-400">
            Each entry names who acted, because a decision has to be answerable for. There
            is deliberately no way to filter or group this by person: the same trail
            aggregated over people would be a report on staff rather than on records.
          </p>
        </>
      )}

      <p className="mt-4 max-w-2xl text-xs text-slate-600 dark:text-slate-400">
        {measureLabel(measures, measure)} only. A change is recorded when a record moves
        between states; editing a field that carries no state records the edit, not a
        transition.
      </p>
    </>
  )
}

function KindLink({
  label,
  count,
  query,
  current,
}: {
  label: string
  count: number
  query: Record<string, string | undefined>
  current: boolean
}) {
  return (
    <Link
      href={{ pathname: HERE, query }}
      aria-current={current ? 'true' : undefined}
      className={
        'rounded-md border px-3 py-1.5 text-sm transition ' +
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
        'focus-visible:outline-sky-600 ' +
        (current
          ? 'border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-100'
          : 'border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800')
      }
    >
      {label} <span className="tabular-nums text-slate-500">{formatCount(count)}</span>
    </Link>
  )
}

function ChangeRow({ entry, measure }: { entry: ChangeEntry; measure: string }) {
  const moved = summariseFields(entry.changed)
  const when = formatDate(entry.at)

  return (
    <li className="border-b border-slate-200 py-4 last:border-0 dark:border-slate-800">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-medium text-slate-900 dark:text-slate-50">
          {actionLabel(entry.action)}
          {entry.entity_label ? (
            <span className="font-normal text-slate-600 dark:text-slate-400">
              {' — '}
              {entry.entity_label}
            </span>
          ) : null}
        </p>
        {when ? (
          <time
            dateTime={isoDate(entry.at)}
            className="text-xs text-slate-600 dark:text-slate-400"
          >
            {when}
          </time>
        ) : null}
      </div>

      {moved ? (
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{moved}</p>
      ) : null}

      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-600 dark:text-slate-400">
        {/* Who is answerable. Named here and nowhere aggregated. */}
        <span>{entry.actor ?? 'No actor recorded'}</span>

        {entry.evidence_id ? (
          <>
            <span aria-hidden="true">·</span>
            <Link
              href={`/workspace/evidence/${entry.evidence_id}`}
              className={`${LINK} text-slate-700 dark:text-slate-300`}
            >
              the evidence this rests on
            </Link>
          </>
        ) : null}

        {entry.entity_id && measure === 'evidence' ? (
          <>
            <span aria-hidden="true">·</span>
            <Link
              href={`/workspace/evidence/${entry.entity_id}`}
              className={`${LINK} text-slate-700 dark:text-slate-300`}
            >
              open the record
            </Link>
          </>
        ) : null}

        {entry.entity_id && measure === 'questions' ? (
          <>
            <span aria-hidden="true">·</span>
            <Link
              href={`/workspace/questions/${entry.entity_id}`}
              className={`${LINK} text-slate-700 dark:text-slate-300`}
            >
              open the record
            </Link>
          </>
        ) : null}
      </div>
    </li>
  )
}
