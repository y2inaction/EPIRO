import type { Metadata } from 'next'

import { getOverview } from '@/lib/workspace'
import { FigurePage } from './_figures'

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
export default function IntelligencePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  return (
    <FigurePage
      title="Intelligence"
      description="Counts of your organisations' own records — what they have evidenced, been asked and done. Every figure is a link to the records it counted."
      current="/workspace/intelligence"
      searchParams={searchParams}
      fetchFigures={getOverview}
      footnote="Every figure is a count as of now. Nothing here is saved or published — these are read from the records each time a page is opened."
    />
  )
}
