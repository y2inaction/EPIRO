import type { Metadata } from 'next'

import { IntelligenceSection } from '../_section'

export const metadata: Metadata = {
  title: 'Integrity intelligence',
}

export default function IntegrityIntelligencePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  return (
    <IntelligenceSection
      measure="integrity_signals"
      current="/workspace/intelligence/integrity"
      searchParams={searchParams}
    />
  )
}
