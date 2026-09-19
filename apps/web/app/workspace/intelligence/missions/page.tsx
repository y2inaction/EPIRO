import type { Metadata } from 'next'

import { IntelligenceSection } from '../_section'

export const metadata: Metadata = {
  title: 'Missions intelligence',
}

export default function MissionsIntelligencePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  return (
    <IntelligenceSection
      measure="missions"
      current="/workspace/intelligence/missions"
      searchParams={searchParams}
    />
  )
}
