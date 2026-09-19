import type { Metadata } from 'next'

import { IntelligenceSection } from '../_section'

export const metadata: Metadata = {
  title: 'Missions intelligence',
}

export default function MissionsIntelligencePage() {
  return (
    <IntelligenceSection measure="missions" current="/workspace/intelligence/missions" />
  )
}
