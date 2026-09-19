import Link from 'next/link'

import { filterLabel, type FilterSet } from '@/lib/intelligence'
import type { Named } from '@/lib/workspace'
import type { SectionHref } from '@/components/IntelligenceNav'

/**
 * Narrow every figure on the page.
 *
 * A plain GET form rather than a client component. The filters end up in the
 * URL, which is what makes a filtered view something a person can bookmark,
 * send to a colleague, or land on from a link and see the same numbers — and
 * it means the whole thing works with scripting off.
 *
 * Only the filters the current measure can honour are offered. The API
 * refuses one it cannot apply rather than ignoring it, which is right, so a
 * bar that offered everything everywhere would break every section whose
 * measure lacks that column.
 */
export function FilterBar({
  action,
  filters,
  available,
  organisations,
  areas,
  themes,
  statuses,
  verificationStates,
}: {
  action: SectionHref
  filters: FilterSet
  /** Filter names this page can apply, from the measure catalogue. */
  available: string[]
  organisations: Named[]
  areas: Named[]
  themes: Named[]
  /** Status values this measure actually uses, from its own breakdown. */
  statuses?: string[]
  verificationStates?: string[]
}) {
  const offers = (name: string) => available.includes(name)
  const anySet = Object.values(filters).some(Boolean)

  return (
    <form
      action={action}
      method="get"
      className="mb-8 rounded-xl border border-slate-200 p-4 dark:border-slate-800"
    >
      <div className="flex flex-wrap items-end gap-4">
        {offers('organisation_id') && organisations.length > 1 ? (
          <Choice
            name="organisation_id"
            value={filters.organisation_id}
            options={organisations.map((o) => ({ value: o.id, label: o.name }))}
            anyLabel="All you belong to"
          />
        ) : null}

        {offers('geography_id') && areas.length > 0 ? (
          <Choice
            name="geography_id"
            value={filters.geography_id}
            options={areas.map((a) => ({ value: a.id, label: a.name }))}
            anyLabel="Anywhere"
          />
        ) : null}

        {offers('thematic_area_id') && themes.length > 0 ? (
          <Choice
            name="thematic_area_id"
            value={filters.thematic_area_id}
            options={themes.map((t) => ({ value: t.id, label: t.name }))}
            anyLabel="Any theme"
          />
        ) : null}

        {offers('verification_status') && verificationStates?.length ? (
          <Choice
            name="verification_status"
            value={filters.verification_status}
            options={verificationStates.map((s) => ({ value: s, label: s.replace(/_/g, ' ') }))}
            anyLabel="Any state"
          />
        ) : null}

        {offers('status') && statuses?.length ? (
          <Choice
            name="status"
            value={filters.status}
            options={statuses.map((s) => ({ value: s, label: s.replace(/_/g, ' ') }))}
            anyLabel="Any status"
          />
        ) : null}

        {offers('since') ? (
          <DateField name="since" value={filters.since} />
        ) : null}
        {offers('until') ? <DateField name="until" value={filters.until} /> : null}

        <button
          type="submit"
          className={
            'rounded-md border border-slate-900 bg-slate-900 px-3 py-1.5 text-sm font-medium ' +
            'text-white transition hover:bg-slate-700 ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 ' +
            'dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300'
          }
        >
          Apply
        </button>

        {anySet ? (
          <Link
            href={action}
            className={
              'text-sm text-slate-700 underline-offset-4 hover:underline ' +
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
              'focus-visible:outline-sky-600 dark:text-slate-300'
            }
          >
            Clear
          </Link>
        ) : null}
      </div>

      {offers('since') || offers('until') ? (
        // Said where the control is, not in a footnote somewhere else. A
        // reader filtering to September and seeing a June handover counted
        // would otherwise think the filter was broken.
        <p className="mt-3 text-xs text-slate-600 dark:text-slate-400">
          Dates are when the platform recorded something, not when it happened.
        </p>
      ) : null}
    </form>
  )
}

const FIELD =
  'rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600 ' +
  'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

const LABEL = 'block text-xs font-medium text-slate-600 dark:text-slate-400'

function Choice({
  name,
  value,
  options,
  anyLabel,
}: {
  name: string
  value?: string
  options: { value: string; label: string }[]
  /** What "no filter" is called. Never an empty option: a blank row in a
      select reads as a missing value rather than as "all of them". */
  anyLabel: string
}) {
  return (
    <div className="space-y-1">
      <label className={LABEL} htmlFor={name}>
        {filterLabel(name)}
      </label>
      <select id={name} name={name} defaultValue={value ?? ''} className={FIELD}>
        <option value="">{anyLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}

function DateField({ name, value }: { name: string; value?: string }) {
  return (
    <div className="space-y-1">
      <label className={LABEL} htmlFor={name}>
        {filterLabel(name)}
      </label>
      <input type="date" id={name} name={name} defaultValue={value ?? ''} className={FIELD} />
    </div>
  )
}

/**
 * What the current page could not apply.
 *
 * A filter silently absent looks exactly like a filter that found nothing, so
 * anything set and not honoured is named here instead.
 */
export function FiltersSetAside({ names }: { names: string[] }) {
  if (names.length === 0) {
    return null
  }

  return (
    <p className="mb-8 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
      Set aside for this measure, which does not record{' '}
      {names.map((name) => filterLabel(name).toLowerCase()).join(' or ')}. The figures below
      are not narrowed by {names.length > 1 ? 'those' : 'that'}.
    </p>
  )
}
