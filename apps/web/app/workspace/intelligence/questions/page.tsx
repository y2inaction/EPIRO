import type { Metadata } from 'next'

import { IntelligenceSection } from '../_section'

export const metadata: Metadata = {
  title: 'Questions intelligence',
}

export default function QuestionsIntelligencePage() {
  return (
    <IntelligenceSection measure="questions" current="/workspace/intelligence/questions" />
  )
}
