/** Presentation helpers shared across the portal. */

/**
 * A date a reader can scan, or null when there is none.
 *
 * Returns null rather than a placeholder so a caller must decide what an
 * absent date means in its own context. "Unknown" and "not yet published"
 * look identical once they are both rendered as a dash.
 */
export function formatDate(value: string | null | undefined): string | null {
  if (!value) {
    return null
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }

  return parsed.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

/** The machine-readable form for a <time> element. */
export function isoDate(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined
  }
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? undefined : parsed.toISOString()
}

/**
 * A short lead-in for a card.
 *
 * Cut on a word boundary and marked with an ellipsis, so it is visible that
 * the text continues rather than that it ends abruptly.
 */
export function excerpt(text: string | null | undefined, maxLength = 180): string {
  if (!text) {
    return ''
  }

  const collapsed = text.replace(/\s+/g, ' ').trim()
  if (collapsed.length <= maxLength) {
    return collapsed
  }

  const cut = collapsed.slice(0, maxLength)
  const lastSpace = cut.lastIndexOf(' ')
  return `${(lastSpace > 0 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`
}

/** A readable count, or null when none was recorded. */
export function formatCount(value: number | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null
  }
  return value.toLocaleString('en-GB')
}

/**
 * How a verification state should be described to a reader.
 *
 * Spec section 11 is explicit that a source is never labelled true. These
 * states describe how far review has got and what it found; none of them is a
 * claim that the content is fact, and the wording here has to keep that
 * distinction rather than quietly turning "verified" into "confirmed".
 */
export interface VerificationLabel {
  label: string
  meaning: string
  tone: 'checked' | 'pending' | 'disputed'
}

const VERIFICATION: Record<string, VerificationLabel> = {
  verified: {
    label: 'Verified',
    meaning: 'Checked against its source by someone other than the author.',
    tone: 'checked',
  },
  in_review: {
    label: 'In review',
    meaning: 'Being checked now. No conclusion has been reached.',
    tone: 'pending',
  },
  unverified: {
    label: 'Unverified',
    meaning: 'Recorded, but not yet checked by anyone.',
    tone: 'pending',
  },
  disputed: {
    label: 'Disputed',
    meaning: 'Checked, and the check raised a conflict that is unresolved.',
    tone: 'disputed',
  },
  rejected: {
    label: 'Rejected',
    meaning: 'Checked, and the record did not hold up.',
    tone: 'disputed',
  },
}

export function verificationLabel(status: string): VerificationLabel {
  return (
    VERIFICATION[status] ?? {
      label: status.replace(/_/g, ' '),
      meaning: 'How far review has got on this record.',
      tone: 'pending',
    }
  )
}

/**
 * How a finding about a circulating claim should be described.
 *
 * Every phrase is about the claim, never about whoever repeated it. Spec
 * section 4 forbids profiling citizens, and wording is where that leaks first:
 * "spread by" or "targeted at" would be the same prohibition broken in prose
 * rather than in a column.
 *
 * "Unresolved" is deliberately not a soft "probably false". It says the body
 * looked and could not settle it, which is the honest state and the one spec
 * section 32 exists to keep available.
 */
const FINDINGS: Record<string, VerificationLabel> = {
  accurate: {
    label: 'Accurate',
    meaning: 'Checked against evidence, and the claim holds up.',
    tone: 'checked',
  },
  misleading: {
    label: 'Misleading',
    meaning: 'Partly true, but framed so that it gives a false impression.',
    tone: 'disputed',
  },
  out_of_context: {
    label: 'Out of context',
    meaning: 'Real material, presented as being about something it is not.',
    tone: 'disputed',
  },
  false: {
    label: 'False',
    meaning: 'Checked against evidence, and the claim does not hold up.',
    tone: 'disputed',
  },
  unsubstantiated: {
    label: 'Unsubstantiated',
    meaning: 'Nothing found that supports it. That is not the same as disproved.',
    tone: 'pending',
  },
  unresolved: {
    label: 'Unresolved',
    meaning: 'Looked into, and it could not be settled either way.',
    tone: 'pending',
  },
}

export function findingLabel(finding: string): VerificationLabel {
  return (
    FINDINGS[finding] ?? {
      label: finding.replace(/_/g, ' '),
      meaning: 'What the assessment concluded about this claim.',
      tone: 'pending',
    }
  )
}
