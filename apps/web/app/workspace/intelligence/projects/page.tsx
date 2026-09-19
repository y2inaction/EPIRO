import type { Metadata } from 'next'

import { IntelligenceSection } from '../_section'

export const metadata: Metadata = {
  title: 'Projects intelligence',
}

export default function ProjectsIntelligencePage() {
  return (
    <IntelligenceSection measure="projects" current="/workspace/intelligence/projects" />
  )
}
