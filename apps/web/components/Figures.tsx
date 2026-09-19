import Link from 'next/link'

import { formatCount } from '@/lib/format'
import {
  barPercent,
  barScale,
  bucketLabelFor,
  COMPLEMENT_NOTE,
  dimensionLabel,
  hasUnresolvedNames,
  suppressedShort,
  suppressionReason,
  recordsQuery,
  type Breakdown,
  type Figure,
  type LabelMap,
} from '@/lib/intelligence'

/**
 * The pieces the intelligence dashboard is drawn from.
 *
 * Two decisions are load-bearing and worth stating where they are made.
 *
 * **Every figure is a link.** A number nobody can check is an assertion, and
 * the API was built so that no figure has to be one: each carries the basis
 * that produced it, and handing that basis back returns the rows. So the
 * number itself is the way through to them.
 *
 * **A withheld figure is not a blank.** Suppression means "there is something
 * here and it is too small to publish". An empty cell says the opposite, so a
 * withheld bucket carries its reason in the space the bar would have used.
 */

const FOCUS =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600'

/**
 * A headline count.
 *
 * A single number is not a chart. Nine of them in a row would be nine bar
 * charts of one bar each, which encodes nothing the digits do not already say,
 * so these are stat tiles.
 */
export function StatTile({
  figure,
  minimumCellSize,
}: {
  figure: Figure
  minimumCellSize: number
}) {
  return (
    <Link
      href={{
        pathname: '/workspace/intelligence/records',
        query: recordsQuery(figure.basis),
      }}
      className={
        'group flex flex-col rounded-xl border border-slate-200 bg-white p-5 transition ' +
        'hover:border-slate-400 dark:border-slate-800 dark:bg-slate-900 ' +
        'dark:hover:border-slate-600 ' +
        FOCUS
      }
    >
      <span className="text-sm text-slate-600 dark:text-slate-400">{figure.label}</span>

      {figure.suppressed ? (
        <>
          <span className="mt-2 text-2xl font-semibold text-slate-500 dark:text-slate-400">
            Withheld
          </span>
          <span className="mt-1 text-xs text-slate-600 dark:text-slate-400">
            {suppressionReason(minimumCellSize)}
          </span>
        </>
      ) : (
        <span className="mt-2 text-4xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
          {formatCount(figure.value)}
        </span>
      )}

      {/* Pushed to the bottom so the affordance lines up across a row of
          tiles whose bodies are different heights. */}
      <span className="mt-auto pt-3 text-xs text-slate-600 underline-offset-4 group-hover:underline dark:text-slate-400">
        See the records this counted →
      </span>
    </Link>
  )
}

/**
 * One measure counted by one of its dimensions.
 *
 * A table rather than a bar chart, and that is the point rather than a
 * shortcut. A withheld bucket cannot be drawn as a bar: zero length would say
 * it is zero, and leaving it out would say it does not exist. Both are lies
 * about a bucket whose only problem is being small. In a table the bar is one
 * column, and a row that has no bar to draw uses that space to say why.
 *
 * Bars are scaled to the largest *reported* bucket. Scaling to a withheld one
 * would let its value be read off the others with a ruler, which is the
 * suppression defeated by geometry rather than by arithmetic.
 *
 * There is no tooltip. A tooltip on a bar exists to reveal the value on
 * hover; here the value is already in the next column, permanently, for
 * everyone — including a reader who cannot hover at all.
 */
export function BreakdownPanel({
  heading,
  breakdown,
  measureName,
  names,
}: {
  heading: string
  breakdown: Breakdown
  measureName: string
  /** Names for a dimension whose buckets are identifiers. */
  names?: LabelMap
}) {
  const scale = barScale(breakdown.figures)
  const dimension = dimensionLabel(breakdown.dimension)
  const unresolved = hasUnresolvedNames(breakdown.figures, breakdown.dimension, names)

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{heading}</h3>
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
        {measureName} by {dimension}
      </p>

      {breakdown.figures.length === 0 ? (
        <p className="mt-4 text-sm text-slate-600 dark:text-slate-400">
          Nothing to count yet. Buckets appear here as records are added.
        </p>
      ) : (
        <table className="mt-4 w-full text-sm">
          {/* The subtitle above already names what this table counts, and a
              caption repeating it makes a screen reader say it twice. This
              carries only what the subtitle does not. */}
          <caption className="sr-only">Each bucket links to the records it counted.</caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">{dimension}</th>
              <th scope="col">Share</th>
              <th scope="col">Records</th>
            </tr>
          </thead>
          <tbody>
            {breakdown.figures.map((figure) => (
              <BreakdownRow
                key={`${figure.basis.dimension}:${figure.basis.value ?? 'none'}:${figure.label}`}
                figure={figure}
                scale={scale}
                minimumCellSize={breakdown.minimum_cell_size}
                dimension={breakdown.dimension}
                names={names}
              />
            ))}
          </tbody>
        </table>
      )}

      {breakdown.suppressed_buckets > 0 ? (
        // Only the part a reader cannot work out for themselves. That a small
        // bucket is withheld is stated once for the whole measure above, and
        // each withheld row says it again in place of its bar; what needs
        // saying here is why a bucket big enough to publish went with it.
        <p className="mt-4 border-t border-slate-200 pt-3 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-400">
          {COMPLEMENT_NOTE}
        </p>
      ) : null}

      {unresolved ? (
        // Said rather than hidden. The count is real; only the name is
        // missing, and a reader who sees an identifier deserves to know that
        // is a lookup failing rather than how the record is stored.
        <p className="mt-4 border-t border-slate-200 pt-3 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-400">
          Some rows show an identifier because no name was found for it. The counts are
          unaffected.
        </p>
      ) : null}
    </section>
  )
}

function BreakdownRow({
  figure,
  scale,
  minimumCellSize,
  dimension,
  names,
}: {
  figure: Figure
  scale: number
  minimumCellSize: number
  dimension: string
  names?: LabelMap
}) {
  const width = barPercent(figure, scale)

  return (
    <tr className="border-b border-slate-100 last:border-0 dark:border-slate-800">
      <th
        scope="row"
        className="max-w-[10rem] truncate py-2 pr-3 text-left align-middle font-normal"
      >
        <Link
          href={{
            pathname: '/workspace/intelligence/records',
            query: recordsQuery(figure.basis),
          }}
          className={
            'rounded-sm text-slate-900 underline-offset-4 hover:underline dark:text-slate-100 ' +
            FOCUS
          }
        >
          {bucketLabelFor(dimension, figure.label, names)}
        </Link>
      </th>

      <td className="w-full py-2 align-middle">
        {figure.suppressed ? (
          // Not a blank. A blank reads as "nothing here", which is the
          // opposite of what a withheld bucket means. The reasoning is under
          // the table; this is enough that the row cannot be misread.
          <span className="text-xs text-slate-600 dark:text-slate-400">
            {suppressedShort(minimumCellSize)}
          </span>
        ) : (
          // Anchored to the left baseline every other bar shares, with only
          // the data end rounded. Zero draws nothing: zero length is the
          // honest picture of zero, and the count beside it says so.
          <span
            className="block h-2 rounded-r-[4px] bg-viz-series dark:bg-viz-series-dark"
            style={{ width: `${width}%` }}
          />
        )}
      </td>

      <td className="py-2 pl-3 text-right align-middle tabular-nums text-slate-900 dark:text-slate-100">
        {figure.suppressed ? (
          <span className="text-xs text-slate-600 dark:text-slate-400">Withheld</span>
        ) : (
          formatCount(figure.value)
        )}
      </td>
    </tr>
  )
}
