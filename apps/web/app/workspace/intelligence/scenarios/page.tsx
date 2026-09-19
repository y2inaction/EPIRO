import type { Metadata } from 'next'

import { IntelligenceSection } from '../_section'

export const metadata: Metadata = {
  title: 'Scenarios intelligence',
}

export default function ScenariosIntelligencePage() {
  return (
    <IntelligenceSection measure="scenarios" current="/workspace/intelligence/scenarios" />
  )
}
