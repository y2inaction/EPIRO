import type { Metadata } from 'next'

import { IntelligenceSection } from '../_section'

export const metadata: Metadata = {
  title: 'Integrity intelligence',
}

export default function IntegrityIntelligencePage() {
  return (
    <IntelligenceSection measure="integrity_signals" current="/workspace/intelligence/integrity" />
  )
}
