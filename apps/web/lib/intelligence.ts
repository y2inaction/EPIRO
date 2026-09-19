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

/**
 * How a figure was narrowed before anything was counted.
 *
 * The same six the API offers. Which of them a measure can honour differs —
 * only evidence carries a verification state, only three measures carry a
 * theme — so the catalogue says per measure, and a filter a measure cannot
 * honour is refused rather than quietly dropped.
 */
export interface FilterSet {
  organisation_id?: string
  geography_id?: string
  thematic_area_id?: string
  verification_status?: string
  status?: string
  since?: string
  until?: string
}

export const FILTER_NAMES = [
  'organisation_id',
  'geography_id',
  'thematic_area_id',
  'verification_status',
  'status',
  'since',
  'until',
] as const

/**
 * What a figure counted, in the form that resolves it back to rows.
 *
 * Carries the filters as well as the measure and dimension, because the API
 * puts them there: a figure narrowed by something its basis did not carry
 * would not reconcile with its own drill-down.
 */
export interface FigureBasis extends FilterSet {
  measure: string
  dimension?: string | null
  value?: string | null
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
  /**
   * Measures left out because a filter was applied that they cannot honour.
   *
   * Named rather than silently missing: a figure absent from a list and a
   * figure that counted nothing look identical and mean opposite things.
   */
  excluded_measures: string[]
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

/**
 * One field that moved, and where it moved from and to.
 *
 * `had_previous` is false where the trail recorded only what the field
 * became. "It was empty" and "nobody wrote down what it was" are different
 * facts, and rendering them the same puts an assertion in the trail's mouth.
 */
export interface FieldChange {
  field: string
  from?: unknown
  to?: unknown
  had_previous?: boolean
}

/** One recorded change: what, when, to which record, and by whom. */
export interface ChangeEntry {
  id: string
  action: string
  at: string
  entity_type: string
  entity_id: string | null
  entity_label: string | null
  actor: string | null
  evidence_id: string | null
  changed: FieldChange[]
}

export interface ChangeFeed {
  measure: string
  total: number
  page: number
  page_size: number
  total_pages: number
  basis: FigureBasis
  by_action: Figure[]
  data: ChangeEntry[]
  date_note: string
}

/** How an action reads in a sentence. */
export function actionLabel(action: string): string {
  const plain = action.includes('.') ? action.split('.').slice(1).join(' ') : action
  return plain.replace(/_/g, ' ')
}

/** A value as it should appear on either side of a change. */
export function changedValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    // "Nothing was there" and "this is blank" are the same fact here, and
    // both are different from a value the reader simply cannot see.
    return 'not set'
  }
  return String(value).replace(/_/g, ' ')
}

/**
 * What moved, in one line.
 *
 * The trail stores whole snapshots and the API sends the difference; this is
 * only the wording. An action with no field difference — a mission check-in,
 * say — returns an empty string rather than an empty bracket, so the row
 * shows the action alone instead of a sentence that trails off.
 */
export function summariseFields(changed: FieldChange[]): string {
  return changed
    .map((change) => {
      const name = dimensionLabel(change.field)
      const to = changedValue(change.to)

      // No left-hand side where the trail never recorded one. Writing "not
      // set → verified" would claim the field had been empty, which the
      // trail does not say and which is usually untrue.
      return change.had_previous === false
        ? `${name} → ${to}`
        : `${name}: ${changedValue(change.from)} → ${to}`
    })
    .join(' · ')
}

export interface MeasureInfo {
  name: string
  label: string
  dimensions: string[]
  /** Which of the six filters this measure can honour. */
  filters: string[]
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
  // Every filter the figure was narrowed by travels with it. Dropping one
  // here would send the reader to a wider set of records than the number
  // they clicked on counted.
  for (const name of FILTER_NAMES) {
    const value = basis[name]
    if (value) {
      query[name] = value
    }
  }
  return query
}

/** Only the filters that are set, as query parameters. */
export function activeFilters(filters: FilterSet): Record<string, string> {
  const active: Record<string, string> = {}
  for (const name of FILTER_NAMES) {
    const value = filters[name]
    if (value) {
      active[name] = value
    }
  }
  return active
}

/**
 * Drop the filters a measure cannot honour.
 *
 * The API refuses one rather than ignoring it, which is right — but a filter
 * bar that stays put while you move between sections would then break every
 * section whose measure lacks that column. So the client sends only what the
 * measure takes, and says which ones it had to set aside.
 */
export function filtersFor(filters: FilterSet, supported: string[]): FilterSet {
  const kept: FilterSet = {}
  for (const name of FILTER_NAMES) {
    if (filters[name] && supported.includes(name)) {
      kept[name] = filters[name]
    }
  }
  return kept
}

/** The filters that were set but this measure cannot honour. */
export function unsupportedFilters(filters: FilterSet, supported: string[]): string[] {
  return FILTER_NAMES.filter((name) => filters[name] && !supported.includes(name))
}

/**
 * The filters a page was asked for, read from its query string.
 *
 * Filters live in the URL rather than in component state: a filtered view is
 * then something a person can bookmark and send to a colleague, and every
 * page lands on the same numbers.
 */
export function filtersFromParams(params: Record<string, string | undefined>): FilterSet {
  const filters: FilterSet = {}
  for (const name of FILTER_NAMES) {
    const value = params[name]
    if (value) {
      filters[name] = value
    }
  }
  return filters
}

/** A filter name as a reader would say it. */
export function filterLabel(name: string): string {
  return (
    {
      organisation_id: 'Organisation',
      geography_id: 'Area',
      thematic_area_id: 'Theme',
      verification_status: 'Verification state',
      status: 'Status',
      since: 'Recorded from',
      until: 'Recorded to',
    }[name] ?? name.replace(/_id$/, '').replace(/_/g, ' ')
  )
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
