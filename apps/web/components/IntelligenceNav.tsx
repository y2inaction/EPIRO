import Link from 'next/link'

import { activeFilters, filtersFor, type FilterSet } from '@/lib/intelligence'

/**
 * Filters that mean the same thing on every page here, and so travel with a
 * reader who moves between them.
 *
 * Status and verification state deliberately do not. "Published" means one
 * thing for evidence and another for a question, so carrying one across would
 * quietly change what it selected; they stay on the section that set them.
 */
const TRAVELS = ['organisation_id', 'geography_id', 'since', 'until']

/**
 * The sections of the intelligence hub.
 *
 * A literal union rather than strings built at runtime: typed routes can only
 * check a destination it can see, and a link assembled from a variable is a
 * 404 nobody finds until somebody clicks it.
 *
 * `measure` is the name the API knows a section by, which is not always the
 * word in the nav — "Integrity" is `integrity_signals` on the server. The
 * mapping lives here once rather than in six page files.
 */
export const SECTIONS = [
  { href: '/workspace/intelligence', label: 'Overview', measure: null },
  { href: '/workspace/intelligence/unresolved', label: 'Unresolved', measure: null },
  { href: '/workspace/intelligence/changes', label: 'Changes', measure: null },
  { href: '/workspace/intelligence/evidence', label: 'Evidence', measure: 'evidence' },
  { href: '/workspace/intelligence/questions', label: 'Questions', measure: 'questions' },
  { href: '/workspace/intelligence/integrity', label: 'Integrity', measure: 'integrity_signals' },
  { href: '/workspace/intelligence/missions', label: 'Missions', measure: 'missions' },
  { href: '/workspace/intelligence/scenarios', label: 'Scenarios', measure: 'scenarios' },
  { href: '/workspace/intelligence/projects', label: 'Projects', measure: 'projects' },
  { href: '/workspace/intelligence/records', label: 'Records', measure: null },
] as const

export type SectionHref = (typeof SECTIONS)[number]['href']

/**
 * Where you are in the hub.
 *
 * `current` is passed in rather than read from the router, which would make
 * this a client component and ship the whole nav to the browser for a link
 * list that never changes.
 */
export function IntelligenceNav({
  current,
  filters = {},
}: {
  current: SectionHref
  /** Carried onto every section, so a filtered view stays filtered. */
  filters?: FilterSet
}) {
  const carried = activeFilters(filtersFor(filters, TRAVELS))

  return (
    <nav aria-label="Intelligence" className="mb-8 flex flex-wrap gap-2">
      {SECTIONS.map((section) => {
        const here = section.href === current

        return (
          <Link
            key={section.href}
            href={{ pathname: section.href, query: carried }}
            aria-current={here ? 'page' : undefined}
            className={
              'rounded-md border px-3 py-1.5 text-sm transition ' +
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
              'focus-visible:outline-sky-600 ' +
              (here
                ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                : 'border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800')
            }
          >
            {section.label}
          </Link>
        )
      })}
    </nav>
  )
}
