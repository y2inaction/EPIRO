import type { Metadata } from 'next'

import { getUnresolved } from '@/lib/workspace'
import { FigurePage } from '../_figures'

export const metadata: Metadata = {
  title: 'Unresolved',
}

/**
 * What is open: recorded, and not taken to a conclusion yet.
 *
 * The counterpart to the overview. A dashboard is usually worst at this
 * question, because finished work is easy to count and waiting work is not —
 * so it gets a page rather than a corner of one.
 *
 * Every figure here is a single open state, which is what lets each one drill
 * down to exactly the records waiting. A broader definition would read better
 * in a heading and could not be checked against its own rows.
 */
export default function UnresolvedPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  return (
    <FigurePage
      title="Unresolved"
      description="What has been recorded and not yet taken to a conclusion. Every figure is a link to the records still waiting."
      current="/workspace/intelligence/unresolved"
      searchParams={searchParams}
      fetchFigures={getUnresolved}
      footnote="Each figure counts one open state, so it can be checked against the records it names. A record waiting for something this list does not name will not appear here."
    />
  )
}
