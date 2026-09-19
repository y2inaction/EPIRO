import { redirect } from 'next/navigation'

import { BreakdownPanel } from '@/components/Figures'
import { FilterBar, FiltersSetAside } from '@/components/FilterBar'
import { IntelligenceNav, type SectionHref } from '@/components/IntelligenceNav'
import { Notice, PageHeading } from '@/components/Shell'
import {
  dimensionLabel,
  filtersFor,
  filtersFromParams,
  isIdentifierDimension,
  measureLabel,
  orderedDimensions,
  unsupportedFilters,
  type LabelMap,
} from '@/lib/intelligence'
import {
  getBreakdown,
  getCurrentUser,
  listMeasures,
  listNamed,
  namesFor,
} from '@/lib/workspace'

/** Dimensions whose values double as a filter's options. */
const OPTION_DIMENSIONS = ['status', 'verification_status'] as const

/**
 * One measure, counted every way the server offers.
 *
 * Shared by the six measure sections, which differ only in which measure they
 * name. The dimensions come from `/intelligence/measures` rather than a list
 * kept here, so a dimension added on the server appears on the screen without
 * this file changing — and one removed stops being offered rather than
 * becoming a panel that 400s. The filters come from the same place, for the
 * same reason.
 *
 * There is deliberately **no total** at the top of a section. A total is a
 * summary figure, and the overview already serves those with the server's own
 * suppression applied. Taking one from the drill-down instead — which is
 * unsuppressed by design, because it answers for records their custodians can
 * already open — would put an unsuppressed aggregate at the top of a summary
 * page. That is precisely the thing the threshold exists to prevent.
 */
export async function IntelligenceSection({
  measure,
  current,
  searchParams,
}: {
  measure: string
  current: SectionHref
  searchParams: Promise<Record<string, string | undefined>>
}) {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const asked = filtersFromParams(await searchParams)

  if (me.value.memberships.length === 0) {
    return (
      <>
        <PageHeading title="Intelligence" />
        <IntelligenceNav current={current} filters={asked} />
        <Notice
          title="There is nothing to count yet"
          detail="These figures cover the organisations you belong to, and you do not belong to one."
        />
      </>
    )
  }

  const catalogue = await listMeasures()

  if (!catalogue.ok) {
    return (
      <>
        <PageHeading title="Intelligence" />
        <IntelligenceNav current={current} filters={asked} />
        <Notice title="This section could not be loaded" detail={catalogue.message} />
      </>
    )
  }

  const spec = catalogue.value.measures.find((m) => m.name === measure)

  if (!spec) {
    // The server decides what can be counted. A section for something it no
    // longer offers says so rather than rendering panels that all refuse.
    return (
      <>
        <PageHeading title={measureLabel(catalogue.value, measure)} />
        <IntelligenceNav current={current} filters={asked} />
        <Notice
          title="This measure is not offered"
          detail={`The server counts: ${catalogue.value.measures.map((m) => m.name).join(', ')}.`}
        />
      </>
    )
  }

  // Only what this measure can honour is sent. The API refuses the rest
  // rather than ignoring them, which is right, so the client narrows the set
  // and says which filters it had to set aside.
  const filters = filtersFor(asked, spec.filters)
  const setAside = unsupportedFilters(asked, spec.filters)
  const dimensions = orderedDimensions(spec.dimensions)
  const optionDimensions = OPTION_DIMENSIONS.filter((d) => spec.dimensions.includes(d))

  const [breakdowns, names, organisations, areas, themes, options] = await Promise.all([
    Promise.all(dimensions.map((dimension) => getBreakdown(measure, dimension, filters))),
    Promise.all(dimensions.map((dimension) => namesFor(dimension))),
    Promise.resolve(
      me.value.memberships.map((m) => ({ id: m.organisation_id, name: m.name })),
    ),
    spec.filters.includes('geography_id') ? listNamed('geography_id') : [],
    spec.filters.includes('thematic_area_id') ? listNamed('thematic_area_id') : [],
    // Deliberately unfiltered. Drawing the options from the filtered
    // breakdown would leave the select holding only the value already
    // chosen, so a reader could narrow once and never change their mind.
    Promise.all(optionDimensions.map((dimension) => getBreakdown(measure, dimension))),
  ])

  const valuesOf = (dimension: string): string[] => {
    const index = optionDimensions.indexOf(dimension as (typeof OPTION_DIMENSIONS)[number])
    const result = index === -1 ? undefined : options[index]
    if (!result?.ok) {
      return []
    }
    return result.value.figures.map((f) => f.label).filter((label) => !label.startsWith('('))
  }

  return (
    <>
      <PageHeading
        title={spec.label}
        description="Counted every way the server offers. Every bucket is a link to the records it counted."
      />

      <IntelligenceNav current={current} filters={asked} />

      <FilterBar
        action={current}
        filters={filters}
        available={spec.filters}
        organisations={organisations}
        areas={areas}
        themes={themes}
        statuses={valuesOf('status')}
        verificationStates={valuesOf('verification_status')}
      />

      <FiltersSetAside names={setAside} />

      {spec.suppressed_below_minimum ? (
        <p className="mb-8 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
          {catalogue.value.suppression_note}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {dimensions.map((dimension, index) => {
          const result = breakdowns[index]
          const heading = `By ${dimensionLabel(dimension)}`

          if (!result.ok) {
            return <Notice key={dimension} title={`${heading} failed`} detail={result.message} />
          }

          return (
            <BreakdownPanel
              key={dimension}
              heading={heading}
              breakdown={result.value}
              measureName={spec.label}
              names={identifierNames(dimension, names[index])}
            />
          )
        })}
      </div>
    </>
  )
}

/** Names are only meaningful for a dimension whose buckets are identifiers. */
function identifierNames(dimension: string, names: LabelMap): LabelMap | undefined {
  return isIdentifierDimension(dimension) ? names : undefined
}
