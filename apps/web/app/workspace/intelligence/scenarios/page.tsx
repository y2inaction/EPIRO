import type { Metadata } from 'next'

import { IntelligenceSection } from '../_section'

export const metadata: Metadata = {
  title: 'Scenarios intelligence',
}

export default function ScenariosIntelligencePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  return (
    <IntelligenceSection
      measure="scenarios"
      current="/workspace/intelligence/scenarios"
      searchParams={searchParams}
    />
  )
}
