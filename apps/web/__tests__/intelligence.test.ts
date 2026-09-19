import {
  barPercent,
  barScale,
  basisSentence,
  bucketLabel,
  bucketLabelFor,
  describeRecord,
  dimensionLabel,
  filterLabel,
  filtersFor,
  filtersFromParams,
  hasUnresolvedNames,
  isIdentifierDimension,
  orderedDimensions,
  measureLabel,
  recordsQuery,
  suppressedShort,
  suppressesSmallBuckets,
  suppressionReason,
  unsupportedFilters,
  type Figure,
  type MeasureCatalogue,
} from '@/lib/intelligence'

function figure(label: string, value: number | null, suppressed = false): Figure {
  return {
    label,
    value,
    suppressed,
    basis: { measure: 'questions', dimension: 'category', value: label },
  }
}

const catalogue: MeasureCatalogue = {
  minimum_cell_size: 5,
  suppression_note: 'Counts of records submitted by members of the public are withheld…',
  measures: [
    {
      name: 'evidence',
      label: 'Evidence records',
      dimensions: ['status', 'verification_status'],
      filters: ['organisation_id', 'geography_id', 'status', 'verification_status'],
      suppressed_below_minimum: false,
    },
    {
      name: 'questions',
      label: 'Questions from the public',
      dimensions: ['category', 'status'],
      filters: ['organisation_id', 'geography_id', 'status'],
      suppressed_below_minimum: true,
    },
  ],
}

describe('recordsQuery', () => {
  it('carries the whole basis, so a drill-down asks the same question as the figure', () => {
    const query = recordsQuery({
      measure: 'evidence',
      dimension: 'status',
      value: 'published',
      geography_id: 'area-1',
    })

    expect(query).toEqual({
      measure: 'evidence',
      dimension: 'status',
      value: 'published',
      geography_id: 'area-1',
    })
  })

  it('omits an absent value rather than sending an empty string', () => {
    // A bucket of records with nothing in that column is "IS NULL", which the
    // API answers by the parameter being absent. Sending value='' would ask a
    // different question and return a different set.
    const query = recordsQuery({ measure: 'questions', dimension: 'category', value: null })

    expect(query).toEqual({ measure: 'questions', dimension: 'category' })
    expect('value' in query).toBe(false)
  })

  it('reduces to the measure alone for a headline with no filter', () => {
    expect(recordsQuery({ measure: 'projects' })).toEqual({ measure: 'projects' })
  })
})

describe('barScale', () => {
  it('scales to the largest reported bucket', () => {
    expect(barScale([figure('water', 8), figure('roads', 5)])).toBe(8)
  })

  it('ignores withheld buckets, so a bar length cannot leak one', () => {
    // If the scale came from a suppressed bucket, every other bar's length
    // would be measurable against it and the withheld number recoverable with
    // a ruler — the suppression defeated by geometry instead of arithmetic.
    const figures = [figure('water', 8), figure('sanitation', null, true)]

    expect(barScale(figures)).toBe(8)
  })

  it('is zero when nothing is reported', () => {
    expect(barScale([figure('sanitation', null, true)])).toBe(0)
  })
})

describe('barPercent', () => {
  it('draws the largest bucket full width', () => {
    expect(barPercent(figure('water', 8), 8)).toBe(100)
  })

  it('keeps a tiny bucket visible rather than indistinguishable from zero', () => {
    expect(barPercent(figure('roads', 1), 1000)).toBe(2)
  })

  it('draws nothing for a genuine zero', () => {
    expect(barPercent(figure('sanitation', 0), 8)).toBe(0)
  })

  it('draws nothing for a withheld bucket', () => {
    // A bar of any length is a number, and this one is being withheld.
    expect(barPercent(figure('sanitation', null, true), 8)).toBe(0)
  })

  it('draws nothing when there is no scale to draw against', () => {
    expect(barPercent(figure('water', 3), 0)).toBe(0)
  })
})

describe('suppressionReason', () => {
  it('says there is something here and why it is not shown', () => {
    const reason = suppressionReason(5)

    expect(reason).toContain('fewer than 5')
    expect(reason).toContain('describe individuals')
    // The one thing it must never be is empty: a blank reads as "nothing
    // here", which is the opposite of what suppression means.
    expect(reason.trim().length).toBeGreaterThan(0)
  })

  it('has a short form that still says there is something here', () => {
    expect(suppressedShort(5)).toBe('Fewer than 5 records')
    expect(suppressedShort(5).trim().length).toBeGreaterThan(0)
  })
})

describe('measureLabel', () => {
  it('uses the label the server serves, not a copy kept here', () => {
    expect(measureLabel(catalogue, 'questions')).toBe('Questions from the public')
  })

  it('falls back to a readable name when the catalogue could not be fetched', () => {
    expect(measureLabel(null, 'integrity_signals')).toBe('integrity signals')
  })
})

describe('suppressesSmallBuckets', () => {
  it('is true only where the server actually suppresses', () => {
    expect(suppressesSmallBuckets(catalogue, 'questions')).toBe(true)
    expect(suppressesSmallBuckets(catalogue, 'evidence')).toBe(false)
  })

  it('claims no protection when the catalogue is unavailable', () => {
    // Telling a reader their records are protected when that is unverified
    // would be worse than saying nothing.
    expect(suppressesSmallBuckets(null, 'questions')).toBe(false)
  })
})

describe('dimensionLabel', () => {
  it('reads as a person would say it', () => {
    expect(dimensionLabel('verification_status')).toBe('verification status')
  })

  it('drops the identifier suffix', () => {
    expect(dimensionLabel('thematic_area_id')).toBe('thematic area')
  })
})

describe('bucketLabel', () => {
  it('humanises an enum value', () => {
    expect(bucketLabel('in_review')).toBe('in review')
  })

  it('leaves the server’s own wording for an empty column alone', () => {
    expect(bucketLabel('(not recorded)')).toBe('(not recorded)')
  })
})

describe('recordsQuery, with filters', () => {
  it('carries every filter the figure was narrowed by', () => {
    // Dropping one here sends the reader to a wider set of records than the
    // number they clicked on counted.
    const query = recordsQuery({
      measure: 'evidence',
      dimension: 'status',
      value: 'published',
      organisation_id: 'org-1',
      geography_id: 'area-1',
      thematic_area_id: 'theme-1',
      verification_status: 'verified',
      since: '2026-09-01',
      until: '2026-09-30',
    })

    expect(query).toEqual({
      measure: 'evidence',
      dimension: 'status',
      value: 'published',
      organisation_id: 'org-1',
      geography_id: 'area-1',
      thematic_area_id: 'theme-1',
      verification_status: 'verified',
      since: '2026-09-01',
      until: '2026-09-30',
    })
  })
})

describe('filtersFromParams', () => {
  it('reads only the filters, ignoring everything else in the query string', () => {
    expect(
      filtersFromParams({ geography_id: 'area-1', page: '3', measure: 'evidence' }),
    ).toEqual({ geography_id: 'area-1' })
  })

  it('treats an empty value as unset, so a cleared select does not filter', () => {
    expect(filtersFromParams({ geography_id: '', status: 'published' })).toEqual({
      status: 'published',
    })
  })
})

describe('filtersFor', () => {
  it('sends only what the measure can honour', () => {
    // The API refuses a filter it cannot apply rather than ignoring it, which
    // is right — so a bar that stayed put across sections would break every
    // one whose measure lacks that column.
    expect(
      filtersFor(
        { geography_id: 'area-1', verification_status: 'verified' },
        ['organisation_id', 'geography_id'],
      ),
    ).toEqual({ geography_id: 'area-1' })
  })

  it('names what it set aside, so a dropped filter is never silent', () => {
    expect(
      unsupportedFilters({ geography_id: 'a', verification_status: 'verified' }, [
        'geography_id',
      ]),
    ).toEqual(['verification_status'])
  })

  it('sets nothing aside when every filter applies', () => {
    expect(unsupportedFilters({ geography_id: 'a' }, ['geography_id'])).toEqual([])
  })
})

describe('filterLabel', () => {
  it('names a filter the way a person would', () => {
    expect(filterLabel('thematic_area_id')).toBe('Theme')
    expect(filterLabel('since')).toBe('Recorded from')
  })
})

describe('isIdentifierDimension', () => {
  it('knows which dimensions come back as identifiers rather than words', () => {
    expect(isIdentifierDimension('geography_id')).toBe(true)
    expect(isIdentifierDimension('thematic_area_id')).toBe(true)
    expect(isIdentifierDimension('status')).toBe(false)
  })
})

describe('bucketLabelFor', () => {
  const names = { 'area-1': 'Kano State' }

  it('resolves an identifier to the name it stands for', () => {
    expect(bucketLabelFor('geography_id', 'area-1', names)).toBe('Kano State')
  })

  it('shows the identifier when no name was found, rather than hiding the row', () => {
    // The count is real. Dropping or blanking the bucket would be the same
    // lie as omitting a suppressed one; the panel says the name is missing.
    expect(bucketLabelFor('geography_id', 'area-9', names)).toBe('area-9')
  })

  it('leaves an empty column alone', () => {
    expect(bucketLabelFor('geography_id', '(not recorded)', names)).toBe('(not recorded)')
  })

  it('never looks up a dimension whose buckets are already words', () => {
    expect(bucketLabelFor('status', 'in_review', { in_review: 'Wrong' })).toBe('in review')
  })
})

describe('hasUnresolvedNames', () => {
  const figure = (label: string) => ({
    label,
    value: 1,
    suppressed: false,
    basis: { measure: 'evidence', dimension: 'geography_id', value: label },
  })

  it('is true when a bucket is still showing a bare identifier', () => {
    expect(hasUnresolvedNames([figure('area-9')], 'geography_id', { 'area-1': 'Kano' })).toBe(true)
  })

  it('is false when every identifier resolved', () => {
    expect(hasUnresolvedNames([figure('area-1')], 'geography_id', { 'area-1': 'Kano' })).toBe(false)
  })

  it('does not count the empty-column bucket as unresolved', () => {
    expect(hasUnresolvedNames([figure('(not recorded)')], 'geography_id', {})).toBe(false)
  })

  it('never applies to a dimension whose buckets are words', () => {
    expect(hasUnresolvedNames([figure('published')], 'status', undefined)).toBe(false)
  })
})

describe('orderedDimensions', () => {
  it('puts the dimensions a reader can scan before the ones needing a lookup', () => {
    expect(orderedDimensions(['geography_id', 'status', 'thematic_area_id', 'category'])).toEqual([
      'category',
      'status',
      'geography_id',
      'thematic_area_id',
    ])
  })

  it('leaves the caller’s array alone', () => {
    const given = ['geography_id', 'status']
    orderedDimensions(given)

    expect(given).toEqual(['geography_id', 'status'])
  })
})

describe('basisSentence', () => {
  it('describes a headline as the whole measure', () => {
    expect(basisSentence({ measure: 'evidence' }, 'Evidence records')).toBe('Evidence records')
  })

  it('names the filter that produced a figure', () => {
    expect(
      basisSentence(
        { measure: 'evidence', dimension: 'status', value: 'published' },
        'Evidence records',
      ),
    ).toBe('Evidence records where status is published')
  })

  it('distinguishes an empty column from a value', () => {
    expect(
      basisSentence({ measure: 'questions', dimension: 'category', value: null }, 'Questions'),
    ).toBe('Questions with no category recorded')
  })

  it('says an area filter includes everything beneath it', () => {
    expect(basisSentence({ measure: 'projects', geography_id: 'area-1' }, 'Projects')).toBe(
      'Projects in the chosen area and everything beneath it',
    )
  })
})

describe('describeRecord', () => {
  it('finds the title field each measure actually uses', () => {
    expect(describeRecord('questions', { id: 'q1', question_text: 'When?' }).title).toBe('When?')
    expect(describeRecord('integrity_signals', { id: 's1', claim: 'Cancelled' }).title).toBe(
      'Cancelled',
    )
    expect(describeRecord('projects', { id: 'p1', name: 'Boreholes' }).title).toBe('Boreholes')
  })

  it('carries the reference and state as supporting facts', () => {
    const summary = describeRecord('evidence', {
      id: 'e1',
      title: 'Handover record',
      reference: 'EV-2026-000001',
      status: 'published',
      verification_status: 'in_review',
    })

    // "published" and "in review" would read as two states of the same thing
    // if the second were not named. They are different axes: one is where the
    // record is in its lifecycle, the other how far checking has got.
    expect(summary.meta).toEqual(['EV-2026-000001', 'published', 'in review verification'])
  })

  it('offers no link for a measure with no screen, rather than one that 404s', () => {
    expect(describeRecord('missions', { id: 'm1', title: 'Kano ward survey' }).route).toBeNull()
    expect(describeRecord('evidence', { id: 'e1', title: 'Handover' }).route).toBe('evidence')
  })

  it('renders a row whose title field is missing without crashing', () => {
    expect(describeRecord('evidence', { id: 'e1' }).title).toBe('Untitled record')
  })
})
