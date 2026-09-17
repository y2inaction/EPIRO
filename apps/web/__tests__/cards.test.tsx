import { render, screen } from '@testing-library/react'

import { EvidenceCard, QuestionCard, StoryCard } from '@/components/Cards'
import { VerificationBadge } from '@/components/VerificationBadge'
import type { PublicEvidence, PublicQuestion, PublicStory } from '@/lib/api'

const story: PublicStory = {
  id: 'story-1',
  title: 'Borehole rehabilitated in Kano',
  headline: 'Twelve boreholes returned to service',
  summary: 'A summary of what happened.',
  body: 'The full body of the story.',
  language: 'en',
  featured: false,
  published_date: '2026-06-01T00:00:00Z',
  evidence_reference: 'EV-2026-000001',
  organisation: { id: 'org-1', name: 'Water Directorate', code: 'water' },
}

const evidence: PublicEvidence = {
  id: 'evidence-1',
  reference: 'EV-2026-000001',
  title: 'Borehole handover record',
  description: 'Handed over in June and running.',
  outcome: 'Twelve boreholes in service.',
  evidence_date: '2026-06-01',
  verification_status: 'verified',
  beneficiaries: 12500,
  document_url: null,
  tags: ['water'],
  organisation: { id: 'org-1', name: 'Water Directorate', code: 'water' },
}

const question: PublicQuestion = {
  id: 'question-1',
  category: 'water',
  question_text: 'When will the borehole be fixed?',
  response: 'It was rehabilitated in June.',
  response_date: '2026-06-10T00:00:00Z',
  language: 'en',
  organisation: { id: 'org-1', name: 'Water Directorate', code: 'water' },
}

describe('StoryCard', () => {
  it('links the title to the story', () => {
    render(<StoryCard story={story} />)

    const link = screen.getByRole('link', { name: story.title })
    expect(link).toHaveAttribute('href', '/stories/story-1')
  })

  it('shows the evidence reference as a link, so a claim can be followed back', () => {
    render(<StoryCard story={story} />)

    const link = screen.getByRole('link', { name: 'EV-2026-000001' })
    expect(link).toHaveAttribute('href', '/evidence/EV-2026-000001')
  })

  it('omits the citation when there is none rather than showing a dead link', () => {
    render(<StoryCard story={{ ...story, evidence_reference: null }} />)

    expect(screen.queryByText(/EV-/)).not.toBeInTheDocument()
  })

  it('marks a featured story', () => {
    render(<StoryCard story={{ ...story, featured: true }} />)

    expect(screen.getByText('Featured')).toBeInTheDocument()
  })
})

describe('EvidenceCard', () => {
  it('is addressed by its permanent reference', () => {
    render(<EvidenceCard record={evidence} />)

    const link = screen.getByRole('link', { name: evidence.title })
    expect(link).toHaveAttribute('href', '/evidence/EV-2026-000001')
  })

  it('shows how far verification got', () => {
    render(<EvidenceCard record={evidence} />)

    expect(screen.getByText('Verified')).toBeInTheDocument()
  })

  it('formats a reach figure', () => {
    render(<EvidenceCard record={evidence} />)

    expect(screen.getByText('12,500 people reached')).toBeInTheDocument()
  })

  it('says nothing about reach when none was recorded', () => {
    render(<EvidenceCard record={{ ...evidence, beneficiaries: null }} />)

    expect(screen.queryByText(/people reached/)).not.toBeInTheDocument()
  })
})

describe('QuestionCard', () => {
  it('shows the question and the answer', () => {
    render(<QuestionCard question={question} />)

    expect(screen.getByText(question.question_text)).toBeInTheDocument()
    expect(screen.getByText(/rehabilitated in June/)).toBeInTheDocument()
  })

  it('names the body that answered, and nobody else', () => {
    render(<QuestionCard question={question} />)

    expect(screen.getByText('Answered by Water Directorate')).toBeInTheDocument()
  })
})

describe('VerificationBadge', () => {
  it('can carry its meaning as visible text', () => {
    // A coloured pill reading "Verified" invites a reader to take it as
    // "true". The meaning has to be available, not just the colour.
    render(<VerificationBadge status="verified" withMeaning />)

    expect(screen.getByText(/Checked against its source/)).toBeInTheDocument()
  })

  it('renders an unknown state without crashing', () => {
    render(<VerificationBadge status="brand_new" />)

    expect(screen.getByText('brand new')).toBeInTheDocument()
  })
})
