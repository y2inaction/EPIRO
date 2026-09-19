/**
 * Presentation rules for the intelligence layer (spec sections 21-22).
 *
 * Separate from lib/workspace.ts, which is server-only. Everything here is
 * pure, so the decisions that matter most on this screen — what a suppressed
 * bucket says instead of showing a blank, how long a bar is drawn, which
 * records a figure resolves to — can be tested directly rather than only
 * through a rendered page.
 *
 * The rule this file exists to keep is the one the API already enforces: a
 * figure is never shown without a way to see what it counted, and a withheld
 * figure explains itself. A blank cell and a zero are different facts.
 */

/** What a figure counted, in the form that resolves it back to rows. */
export interface FigureBasis {
  measure: string
  dimension?: string | null
  value?: string | null
  geography_id?: string | null
}

export interface Figure {
  label: string
  /** Null when withheld. Never confuse this with a zero. */
  value: number | null
  suppressed: boolean
  basis: FigureBasis
}

export interface Overview {
  figures: Figure[]
  minimum_cell_size: number
  suppression_note: string
}

export interface Breakdown {
  measure: string
  dimension: string
  figures: Figure[]
  minimum_cell_size: number
  suppressed_buckets: number
}

export interface RecordPage {
  total: number
  page: number
  page_size: number
  total_pages: number
  basis: FigureBasis
  data: Record<string, unknown>[]
}

export interface MeasureInfo {
  name: string
  label: string
  dimensions: string[]
  suppressed_below_minimum: boolean
}

/**
 * What the server will let a client count.
 *
 * Fetched rather than hard-coded. The API serves this catalogue precisely so a
 * dashboard does not carry its own copy of a list the server enforces, and the
 * two then drift apart without anyone noticing.
 */
export interface MeasureCatalogue {
  minimum_cell_size: number
  suppression_note: string
  measures: MeasureInfo[]
}

export function measureLabel(catalogue: MeasureCatalogue | null, measure: string): string {
  const known = catalogue?.measures.find((m) => m.name === measure)
  return known?.label ?? measure.replace(/_/g, ' ')
}

/**
 * Whether a breakdown of this measure withholds small buckets.
 *
 * Read from the catalogue, so the page explains suppression only where the
 * server actually applies it. Claiming a protection that is not in force
 * would be worse than saying nothing.
 */
export function suppressesSmallBuckets(
  catalogue: MeasureCatalogue | null,
  measure: string,
): boolean {
  return catalogue?.measures.find((m) => m.name === measure)?.suppressed_below_minimum ?? false
}

/** A dimension name as a reader would say it. */
export function dimensionLabel(dimension: string): string {
  return dimension.replace(/_id$/, '').replace(/_/g, ' ')
}

/** A bucket's own label. "(not recorded)" is left exactly as the server sent it. */
export function bucketLabel(value: string): string {
  return value.startsWith('(') ? value : value.replace(/_/g, ' ')
}

/**
 * A dimension whose buckets are identifiers rather than words.
 *
 * Grouping by area or by theme is genuinely useful, but the server can only
 * return the column it grouped on, which is a UUID. Rendered as-is that is a
 * table of identifiers, which answers nothing — so these dimensions need a
 * name resolved for each bucket before they are worth showing.
 */
export function isIdentifierDimension(dimension: string): boolean {
  return dimension.endsWith('_id')
}

/** Identifiers to the names they stand for. */
export type LabelMap = Record<string, string>

/**
 * What a bucket should be called.
 *
 * An identifier with no name resolved is shown as the identifier rather than
 * hidden or blanked: the count is real, and pretending the bucket is not there
 * would be the same lie as omitting a suppressed one. The panel says
 * separately that some names could not be resolved.
 */
export function bucketLabelFor(dimension: string, label: string, names?: LabelMap): string {
  if (!isIdentifierDimension(dimension) || label.startsWith('(')) {
    return bucketLabel(label)
  }
  return names?.[label] ?? label
}

/** Whether any bucket in a breakdown is still showing a bare identifier. */
export function hasUnresolvedNames(figures: Figure[], dimension: string, names?: LabelMap): boolean {
  if (!isIdentifierDimension(dimension)) {
    return false
  }
  return figures.some((f) => !f.label.startsWith('(') && !names?.[f.label])
}

/**
 * The order to show a measure's dimensions in.
 *
 * Taken from the server's own list rather than a copy kept here, so a new
 * dimension appears without this file changing. Only the ordering is a
 * decision: the ones whose buckets are words come before the ones whose
 * buckets are identifiers, because the first kind is read at a glance and the
 * second needs a lookup before it means anything.
 */
export function orderedDimensions(dimensions: string[]): string[] {
  return [...dimensions].sort((a, b) => {
    const byKind = Number(isIdentifierDimension(a)) - Number(isIdentifierDimension(b))
    return byKind !== 0 ? byKind : a.localeCompare(b)
  })
}

/**
 * The query string that resolves a figure back to its records.
 *
 * Only keys the basis actually carries are included. A dimension with no value
 * means "this column is empty", which the API answers with an IS NULL rather
 * than a match on the empty string — so an absent value must stay absent here
 * rather than being sent as ''.
 */
export function recordsQuery(basis: FigureBasis): Record<string, string> {
  const query: Record<string, string> = { measure: basis.measure }
  if (basis.dimension) {
    query.dimension = basis.dimension
  }
  if (basis.value) {
    query.value = basis.value
  }
  if (basis.geography_id) {
    query.geography_id = basis.geography_id
  }
  return query
}

/** What a figure counted, said in a sentence. */
export function basisSentence(basis: FigureBasis, label: string): string {
  const parts = [label]

  if (basis.dimension) {
    const dimension = dimensionLabel(basis.dimension)
    parts.push(
      basis.value
        ? `where ${dimension} is ${bucketLabel(basis.value)}`
        : `with no ${dimension} recorded`,
    )
  }

  if (basis.geography_id) {
    parts.push('in the chosen area and everything beneath it')
  }

  return parts.join(' ')
}

/**
 * The scale a set of bars is drawn against.
 *
 * Reported buckets only. Scaling to a withheld bucket would let its length be
 * read off the others, which is the suppression defeated by geometry instead
 * of by arithmetic.
 */
export function barScale(figures: Figure[]): number {
  return figures.reduce((largest, figure) => {
    if (figure.suppressed || figure.value === null) {
      return largest
    }
    return Math.max(largest, figure.value)
  }, 0)
}

/**
 * How long to draw a bar, as a percentage of the widest.
 *
 * A withheld bucket draws nothing: a bar of any length is a number, and this
 * one is being withheld. A genuine zero also draws nothing, because zero
 * length is the honest picture of zero — the value beside it says so.
 *
 * Anything else gets at least a sliver, so one record against a thousand is a
 * visible mark rather than a bar indistinguishable from a zero.
 */
export function barPercent(figure: Figure, scale: number): number {
  if (figure.suppressed || figure.value === null || figure.value === 0 || scale <= 0) {
    return 0
  }
  return Math.max(2, Math.round((figure.value / scale) * 100))
}

/**
 * What a withheld bucket says in place of a number.
 *
 * The one thing it must never do is render as an empty cell. A blank reads as
 * "nothing here", which is the opposite of what suppression means: there is
 * something here, and it is small enough that publishing it would describe
 * individuals.
 */
export function suppressionReason(minimumCellSize: number): string {
  return (
    `Withheld: fewer than ${minimumCellSize} records, which is small enough to ` +
    'describe individuals rather than a population.'
  )
}

/**
 * The same fact, short enough to sit in a table row.
 *
 * A breakdown can withhold several buckets, and repeating the full reason in
 * each row turns the explanation into wallpaper. The row says enough that it
 * is plainly not a blank; the reasoning sits once beneath the table.
 */
export function suppressedShort(minimumCellSize: number): string {
  return `Fewer than ${minimumCellSize} records`
}

/**
 * Why a bucket large enough to publish can still be withheld.
 *
 * Worth saying on the screen, because a reader who can see the total and the
 * other buckets will otherwise assume a mistake. It is not one: withholding a
 * single bucket leaves it recoverable by subtraction, so a second goes with
 * it.
 */
export const COMPLEMENT_NOTE =
  'When one bucket is withheld a second goes with it, because a single ' +
  'withheld bucket can be recovered by subtracting the others from the total. ' +
  'That is why a bucket large enough to publish is sometimes missing too.'

/** Where a drill-down row can be opened, when a screen for it exists. */
export type RecordRoute = 'evidence' | 'questions' | null

const TITLE_FIELD: Record<string, string> = {
  evidence: 'title',
  questions: 'question_text',
  projects: 'name',
  missions: 'title',
  integrity_signals: 'claim',
  scenarios: 'name',
}

/**
 * Which measures have a workspace screen to open a record on.
 *
 * Deliberately short. Field missions, integrity signals, scenarios and
 * projects have a complete API and no interface yet, so their rows are listed
 * without a link rather than given one that 404s.
 */
const ROUTE: Record<string, RecordRoute> = {
  evidence: 'evidence',
  questions: 'questions',
}

export interface RecordSummary {
  id: string
  title: string
  /** Short facts under the title: a reference, a state, a date. */
  meta: string[]
  route: RecordRoute
}

function text(row: Record<string, unknown>, key: string): string | null {
  const value = row[key]
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

/**
 * One drill-down row, described the same way whatever it counted.
 *
 * The measures return different schemas — evidence has a title and a permanent
 * reference, a question has its text, a signal has the claim — so the page
 * would otherwise need a branch per measure to show a list of rows.
 */
export function describeRecord(measure: string, row: Record<string, unknown>): RecordSummary {
  const id = typeof row.id === 'string' ? row.id : ''
  const titleField = TITLE_FIELD[measure] ?? 'title'
  const meta: string[] = []

  const reference = text(row, 'reference') ?? text(row, 'code')
  if (reference) {
    meta.push(reference)
  }

  const status = text(row, 'status')
  if (status) {
    meta.push(status.replace(/_/g, ' '))
  }

  const verification = text(row, 'verification_status')
  if (verification) {
    meta.push(`${verification.replace(/_/g, ' ')} verification`)
  }

  return {
    id,
    title: text(row, titleField) ?? text(row, 'title') ?? text(row, 'name') ?? 'Untitled record',
    meta,
    route: ROUTE[measure] ?? null,
  }
}
