import { render, screen, within } from '@testing-library/react'

import { BreakdownPanel, StatTile } from '@/components/Figures'
import type { Breakdown, Figure } from '@/lib/intelligence'

const headline: Figure = {
  label: 'Published evidence',
  value: 4,
  suppressed: false,
  basis: { measure: 'evidence', dimension: 'status', value: 'published' },
}

const withheld: Figure = {
  label: 'Questions from the public',
  value: null,
  suppressed: true,
  basis: { measure: 'questions' },
}

function breakdown(figures: Figure[], suppressedBuckets = 0): Breakdown {
  return {
    measure: 'questions',
    dimension: 'category',
    figures,
    minimum_cell_size: 5,
    suppressed_buckets: suppressedBuckets,
  }
}

function bucket(label: string, value: number | null, suppressed = false): Figure {
  return {
    label,
    value,
    suppressed,
    basis: { measure: 'questions', dimension: 'category', value: label },
  }
}

describe('StatTile', () => {
  it('links the number to the records it counted', () => {
    render(<StatTile figure={headline} minimumCellSize={5} />)

    const link = screen.getByRole('link')
    expect(link).toHaveAttribute(
      'href',
      '/workspace/intelligence/records?measure=evidence&dimension=status&value=published',
    )
    expect(within(link).getByText('4')).toBeInTheDocument()
  })

  it('formats a large count so it can be read at a glance', () => {
    render(<StatTile figure={{ ...headline, value: 12500 }} minimumCellSize={5} />)

    expect(screen.getByText('12,500')).toBeInTheDocument()
  })

  it('explains a withheld figure instead of showing a blank', () => {
    render(<StatTile figure={withheld} minimumCellSize={5} />)

    expect(screen.getByText('Withheld')).toBeInTheDocument()
    expect(screen.getByText(/fewer than 5 records/)).toBeInTheDocument()
  })

  it('shows a zero as a zero', () => {
    // "Nobody asked about this" and "too few asked to say" are different
    // facts, and a dashboard that renders them the same is lying about one.
    render(<StatTile figure={{ ...headline, value: 0 }} minimumCellSize={5} />)

    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.queryByText('Withheld')).not.toBeInTheDocument()
  })

  it('still leads to the records when the figure is withheld', () => {
    // Suppression protects the shape of a summary, not the records from the
    // organisation that owns them. The API does not suppress the drill-down,
    // so the tile must not pretend there is nothing to open.
    render(<StatTile figure={withheld} minimumCellSize={5} />)

    expect(screen.getByRole('link')).toHaveAttribute(
      'href',
      '/workspace/intelligence/records?measure=questions',
    )
  })
})

describe('BreakdownPanel', () => {
  it('links every bucket to the records behind it', () => {
    render(
      <BreakdownPanel
        heading="What the public is asking about"
        breakdown={breakdown([bucket('water', 8), bucket('roads', 5)])}
        measureName="Questions from the public"
      />,
    )

    expect(screen.getByRole('link', { name: 'water' })).toHaveAttribute(
      'href',
      '/workspace/intelligence/records?measure=questions&dimension=category&value=water',
    )
  })

  it('shows every count as text, not only as a bar', () => {
    render(
      <BreakdownPanel
        heading="What the public is asking about"
        breakdown={breakdown([bucket('water', 8), bucket('roads', 5)])}
        measureName="Questions from the public"
      />,
    )

    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('gives a withheld bucket its reason in place of a bar', () => {
    render(
      <BreakdownPanel
        heading="What the public is asking about"
        breakdown={breakdown([bucket('water', 8), bucket('sanitation', null, true)], 1)}
        measureName="Questions from the public"
      />,
    )

    const row = screen.getByRole('link', { name: 'sanitation' }).closest('tr')
    expect(row).not.toBeNull()
    expect(within(row as HTMLElement).getByText('Fewer than 5 records')).toBeInTheDocument()
    expect(within(row as HTMLElement).getByText('Withheld')).toBeInTheDocument()
  })

  it('gives the reasoning once beneath the table, not in every withheld row', () => {
    // Two withheld rows each repeating the same paragraph turns the
    // explanation into wallpaper, which is how a reader learns to skip it.
    render(
      <BreakdownPanel
        heading="What the public is asking about"
        breakdown={breakdown(
          [bucket('water', 8), bucket('roads', null, true), bucket('sanitation', null, true)],
          2,
        )}
        measureName="Questions from the public"
      />,
    )

    expect(screen.getAllByText('Fewer than 5 records')).toHaveLength(2)
    expect(screen.getAllByText(/describe individuals rather than a population/)).toHaveLength(1)
  })

  it('explains why a bucket large enough to publish is missing too', () => {
    // Complementary suppression looks like a mistake unless it is named: a
    // reader can see the total and the other buckets, and will assume the
    // dashboard dropped one.
    render(
      <BreakdownPanel
        heading="What the public is asking about"
        breakdown={breakdown([bucket('water', 8), bucket('roads', null, true)], 2)}
        measureName="Questions from the public"
      />,
    )

    expect(screen.getByText(/recovered by subtracting/)).toBeInTheDocument()
  })

  it('says nothing about suppression when none was applied', () => {
    render(
      <BreakdownPanel
        heading="How far checking has got"
        breakdown={{
          ...breakdown([bucket('verified', 3)]),
          measure: 'evidence',
          dimension: 'verification_status',
        }}
        measureName="Evidence records"
      />,
    )

    expect(screen.queryByText(/recovered by subtracting/)).not.toBeInTheDocument()
  })

  it('names what it is counting and how', () => {
    render(
      <BreakdownPanel
        heading="How far checking has got"
        breakdown={{
          ...breakdown([bucket('verified', 3)]),
          measure: 'evidence',
          dimension: 'verification_status',
        }}
        measureName="Evidence records"
      />,
    )

    expect(screen.getByText('Evidence records by verification status')).toBeInTheDocument()
  })

  it('says there is nothing to count rather than drawing an empty table', () => {
    render(
      <BreakdownPanel
        heading="Where field work stands"
        breakdown={breakdown([])}
        measureName="Field missions"
      />,
    )

    expect(screen.getByText(/Nothing to count yet/)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('scales the widest reported bucket to full width', () => {
    const { container } = render(
      <BreakdownPanel
        heading="What the public is asking about"
        breakdown={breakdown([bucket('water', 8), bucket('roads', 2)])}
        measureName="Questions from the public"
      />,
    )

    const bars = container.querySelectorAll('td > span[style]')
    expect(bars[0]).toHaveStyle({ width: '100%' })
    expect(bars[1]).toHaveStyle({ width: '25%' })
  })

  it('draws no bar at all for a withheld bucket', () => {
    const { container } = render(
      <BreakdownPanel
        heading="What the public is asking about"
        breakdown={breakdown([bucket('water', 8), bucket('sanitation', null, true)], 1)}
        measureName="Questions from the public"
      />,
    )

    // One bar for one reported bucket. A withheld bucket with a bar of any
    // length would publish the number the threshold exists to withhold.
    expect(container.querySelectorAll('td > span[style]')).toHaveLength(1)
  })
})
