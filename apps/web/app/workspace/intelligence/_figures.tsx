import { redirect } from 'next/navigation'

import { StatTile } from '@/components/Figures'
import { FilterBar } from '@/components/FilterBar'
import { IntelligenceNav, type SectionHref } from '@/components/IntelligenceNav'
import { Notice, PageHeading } from '@/components/Shell'
import { filtersFromParams, measureLabel, type FilterSet } from '@/lib/intelligence'
import { getCurrentUser, listMeasures, listNamed, type Result } from '@/lib/workspace'
import type { Overview } from '@/lib/intelligence'

/**
 * Filters that every headline measure can honour.
 *
 * The overview and the unresolved list both span measures, and a filter only
 * some of them carry would drop the rest from the list. The API says which
 * ones it dropped and the page would print that, but a reader who picks a
 * theme and watches six of nine figures vanish has been given a worse answer
 * than the one they asked for. Those narrower filters belong on a section,
 * where they apply to everything on the page.
 */
const SHARED_FILTERS = ['organisation_id', 'geography_id', 'since', 'until']

/**
 * A page of headline figures: the overview, or what remains unresolved.
 *
 * Both are the same mechanism — a list of measures each narrowed to one
 * value — so they render the same way. What differs is the question they
 * answer: how much is there, and what is still waiting.
 */
export async function FigurePage({
  title,
  description,
  current,
  searchParams,
  fetchFigures,
  footnote,
}: {
  title: string
  description: string
  current: SectionHref
  searchParams: Promise<Record<string, string | undefined>>
  fetchFigures: (filters: FilterSet) => Promise<Result<Overview>>
  footnote: string
}) {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const user = me.value
  const filters = filtersFromParams(await searchParams)

  if (user.memberships.length === 0) {
    return (
      <>
        <PageHeading title={title} />
        <IntelligenceNav current={current} filters={filters} />
        <Notice
          title="There is nothing to count yet"
          detail="These figures cover the organisations you belong to, and you do not belong to one."
        />
      </>
    )
  }

  const [figures, catalogue, areas] = await Promise.all([
    fetchFigures(filters),
    listMeasures(),
    listNamed('geography_id'),
  ])

  return (
    <>
      <PageHeading title={title} description={description} />

      <IntelligenceNav current={current} filters={filters} />

      <FilterBar
        action={current}
        filters={filters}
        available={SHARED_FILTERS}
        organisations={user.memberships.map((m) => ({ id: m.organisation_id, name: m.name }))}
        areas={areas}
        themes={[]}
      />

      {!figures.ok ? (
        <Notice title="The figures could not be loaded" detail={figures.message} />
      ) : (
        <>
          {figures.value.excluded_measures.length > 0 ? (
            // A figure missing from a list and a figure that counted nothing
            // look identical and mean opposite things.
            <p className="mb-6 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
              Left out because a filter was applied that they do not record:{' '}
              {figures.value.excluded_measures
                .map((name) => measureLabel(catalogue.ok ? catalogue.value : null, name))
                .join(', ')}
              .
            </p>
          ) : null}

          {figures.value.figures.length === 0 ? (
            <Notice
              title="Nothing to show under these filters"
              detail="Every measure was either empty or set aside. Clearing a filter will widen it."
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {figures.value.figures.map((figure) => (
                <StatTile
                  key={figure.label}
                  figure={figure}
                  minimumCellSize={figures.value.minimum_cell_size}
                />
              ))}
            </div>
          )}

          {/* The server's own wording for the rule, rather than a paraphrase
              that could drift from what the code actually does. */}
          <p className="mt-4 max-w-3xl text-xs text-slate-600 dark:text-slate-400">
            {figures.value.suppression_note}
          </p>
        </>
      )}

      <p className="mt-10 max-w-2xl text-xs text-slate-600 dark:text-slate-400">{footnote}</p>
    </>
  )
}
