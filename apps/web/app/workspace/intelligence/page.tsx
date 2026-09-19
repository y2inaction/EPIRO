import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { BreakdownPanel, StatTile } from '@/components/Figures'
import { Notice, PageHeading } from '@/components/Shell'
import { measureLabel, type MeasureCatalogue } from '@/lib/intelligence'
import { getBreakdown, getCurrentUser, getOverview, listMeasures } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Intelligence',
}

/**
 * The breakdowns this screen shows.
 *
 * Fixed rather than chosen by the reader, because there is no dimension picker
 * yet. Each heading is the question the panel answers, which is the point of
 * putting it on a dashboard at all.
 *
 * Only dimensions whose buckets are readable appear here. `geography_id` and
 * `thematic_area_id` are real dimensions the API offers, but their buckets
 * come back as identifiers, and a table of UUIDs is not an answer to
 * anything — they wait for a screen that can resolve a name.
 */
const PANELS = [
  {
    heading: 'How far checking has got',
    measure: 'evidence',
    dimension: 'verification_status',
  },
  {
    heading: 'What the public is asking about',
    measure: 'questions',
    dimension: 'category',
  },
  {
    heading: 'What circulating claims turned out to be',
    measure: 'integrity_signals',
    dimension: 'finding',
  },
  {
    heading: 'Where field work stands',
    measure: 'missions',
    dimension: 'status',
  },
] as const

export default async function IntelligencePage() {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const user = me.value

  if (user.memberships.length === 0) {
    return (
      <>
        <PageHeading title="Intelligence" />
        <Notice
          title="There is nothing to count yet"
          detail="These figures cover the organisations you belong to, and you do not belong to one."
        />
      </>
    )
  }

  // One round trip each, in parallel: the figures are computed on request
  // rather than cached, which is what lets any of them be reconciled against
  // the records at the moment it is read.
  const [overview, catalogue, ...breakdowns] = await Promise.all([
    getOverview(),
    listMeasures(),
    ...PANELS.map((panel) => getBreakdown(panel.measure, panel.dimension)),
  ])

  const measures: MeasureCatalogue | null = catalogue.ok ? catalogue.value : null

  return (
    <>
      <PageHeading
        title="Intelligence"
        description="Counts of your organisations' own records — what they have evidenced, been asked and done. Every figure is a link to the records it counted."
      />

      <p className="mb-8 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
        Covering {user.memberships.map((m) => m.name).join(', ')}
        {user.memberships.length > 1
          ? ' together. Every figure counts all of them at once, because that is how the API scopes them; there is no way to narrow one to a single body from here.'
          : '.'}
      </p>

      <h2 className="mb-4 text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
        Headline figures
      </h2>

      {!overview.ok ? (
        <Notice title="The figures could not be loaded" detail={overview.message} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {overview.value.figures.map((figure) => (
              <StatTile
                key={figure.label}
                figure={figure}
                minimumCellSize={overview.value.minimum_cell_size}
              />
            ))}
          </div>

          {/* The server's own wording for the rule, rather than a paraphrase
              that could drift from what the code actually does. */}
          <p className="mt-4 max-w-3xl text-xs text-slate-600 dark:text-slate-400">
            {overview.value.suppression_note}
          </p>
        </>
      )}

      <h2 className="mb-4 mt-12 text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
        Breakdowns
      </h2>

      <div className="grid gap-4 lg:grid-cols-2">
        {PANELS.map((panel, index) => {
          const result = breakdowns[index]

          if (!result.ok) {
            return (
              <Notice
                key={panel.heading}
                title={`${panel.heading} could not be loaded`}
                detail={result.message}
              />
            )
          }

          return (
            <BreakdownPanel
              key={panel.heading}
              heading={panel.heading}
              breakdown={result.value}
              measureName={measureLabel(measures, panel.measure)}
            />
          )
        })}
      </div>

      {/* Section 81: what this screen does not do, said here rather than left
          for a reader to discover by looking for a control that is not
          there. */}
      <p className="mt-10 max-w-2xl text-xs text-slate-600 dark:text-slate-400">
        Every figure is a count as of now. There is no trend over time, no filter by area,
        and nothing here is saved or published — these are read from the records each time
        the page is opened.
      </p>

      <p className="mt-8">
        <Link
          href="/workspace"
          className={
            'text-sm text-slate-700 underline-offset-4 hover:underline ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 dark:text-slate-300'
          }
        >
          ← Back to the workspace
        </Link>
      </p>
    </>
  )
}
