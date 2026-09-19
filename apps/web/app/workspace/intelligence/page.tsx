import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { StatTile } from '@/components/Figures'
import { IntelligenceNav } from '@/components/IntelligenceNav'
import { Notice, PageHeading } from '@/components/Shell'
import { getCurrentUser, getOverview } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Intelligence',
}

/**
 * The overview of the intelligence hub.
 *
 * Headline figures only. Each measure has a section of its own for the
 * breakdowns, so this page answers "how much of everything is there" and the
 * sections answer "and of what kind".
 *
 * These are the figures the server suppresses where a count is small enough to
 * describe individuals, which is why the totals live here and not at the top
 * of each section: a section would have to get its total from the drill-down,
 * which is unsuppressed by design.
 */
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
        <IntelligenceNav current="/workspace/intelligence" />
        <Notice
          title="There is nothing to count yet"
          detail="These figures cover the organisations you belong to, and you do not belong to one."
        />
      </>
    )
  }

  const overview = await getOverview()

  return (
    <>
      <PageHeading
        title="Intelligence"
        description="Counts of your organisations' own records — what they have evidenced, been asked and done. Every figure is a link to the records it counted."
      />

      <IntelligenceNav current="/workspace/intelligence" />

      <p className="mb-8 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
        Covering {user.memberships.map((m) => m.name).join(', ')}
        {user.memberships.length > 1
          ? ' together. Every figure counts all of them at once, because that is how the API scopes them; there is no way to narrow one to a single body from here.'
          : '.'}
      </p>

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

      {/* Section 81: what this hub does not do, said here rather than left for
          a reader to discover by looking for a control that is not there. */}
      <p className="mt-10 max-w-2xl text-xs text-slate-600 dark:text-slate-400">
        Every figure is a count as of now. There is no trend over time, no filter by area,
        and nothing here is saved or published — these are read from the records each time
        a page is opened.
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
