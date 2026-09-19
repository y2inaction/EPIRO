import type { Metadata } from 'next'

import { IntelligenceSection } from '../_section'

export const metadata: Metadata = {
  title: 'Evidence intelligence',
}

export default function EvidenceIntelligencePage() {
  return (
    <IntelligenceSection measure="evidence" current="/workspace/intelligence/evidence" />
  )
}
