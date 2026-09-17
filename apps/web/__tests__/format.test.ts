import {
  excerpt,
  formatCount,
  formatDate,
  isoDate,
  verificationLabel,
} from '@/lib/format'

describe('formatDate', () => {
  it('renders a date a reader can scan', () => {
    expect(formatDate('2026-06-01T00:00:00Z')).toBe('1 June 2026')
  })

  it('returns null rather than a placeholder when there is no date', () => {
    // "Unknown" and "not yet published" must not render identically.
    expect(formatDate(null)).toBeNull()
    expect(formatDate(undefined)).toBeNull()
    expect(formatDate('')).toBeNull()
  })

  it('returns null for something that is not a date', () => {
    expect(formatDate('not a date')).toBeNull()
  })
})

describe('isoDate', () => {
  it('gives a machine-readable value for a time element', () => {
    expect(isoDate('2026-06-01T00:00:00Z')).toBe('2026-06-01T00:00:00.000Z')
  })

  it('is undefined when there is nothing to mark up', () => {
    expect(isoDate(null)).toBeUndefined()
    expect(isoDate('nonsense')).toBeUndefined()
  })
})

describe('excerpt', () => {
  it('leaves short text alone', () => {
    expect(excerpt('A short summary.')).toBe('A short summary.')
  })

  it('collapses runs of whitespace', () => {
    expect(excerpt('Two  spaces\nand a newline')).toBe('Two spaces and a newline')
  })

  it('cuts on a word boundary and marks the cut', () => {
    const result = excerpt('alpha bravo charlie delta echo', 14)

    expect(result).toBe('alpha bravo…')
    expect(result).not.toContain('charl')
  })

  it('is empty when there is nothing to show', () => {
    expect(excerpt(null)).toBe('')
    expect(excerpt(undefined)).toBe('')
  })
})

describe('formatCount', () => {
  it('groups thousands', () => {
    expect(formatCount(12500)).toBe('12,500')
  })

  it('distinguishes zero from nothing recorded', () => {
    expect(formatCount(0)).toBe('0')
    expect(formatCount(null)).toBeNull()
  })
})

describe('verificationLabel', () => {
  it('never describes a record as true', () => {
    // Spec section 11: the states say how far review got, not that the
    // content is fact. This test exists to fail if that wording drifts.
    for (const status of ['verified', 'in_review', 'unverified', 'disputed', 'rejected']) {
      const { label, meaning } = verificationLabel(status)
      const wording = `${label} ${meaning}`.toLowerCase()

      expect(wording).not.toMatch(/\btrue\b/)
      expect(wording).not.toMatch(/\bfact\b/)
      expect(wording).not.toMatch(/\bproven\b/)
      expect(wording).not.toMatch(/\bconfirmed true\b/)
    }
  })

  it('explains what verified actually means', () => {
    const { label, meaning, tone } = verificationLabel('verified')

    expect(label).toBe('Verified')
    expect(meaning).toContain('Checked against its source')
    expect(tone).toBe('checked')
  })

  it('separates in review from unverified', () => {
    expect(verificationLabel('in_review').label).toBe('In review')
    expect(verificationLabel('unverified').label).toBe('Unverified')
    expect(verificationLabel('in_review').meaning).not.toBe(
      verificationLabel('unverified').meaning,
    )
  })

  it('falls back readably for a state it does not know', () => {
    expect(verificationLabel('some_new_state').label).toBe('some new state')
  })
})
