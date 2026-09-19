import Link from 'next/link'

const NAV = [
  { href: '/stories', label: 'Stories' },
  { href: '/evidence', label: 'Evidence' },
  { href: '/questions', label: 'Questions' },
  { href: '/corrections', label: 'Corrections' },
  { href: '/search', label: 'Search' },
] as const

// Separated from the portal nav: this is the staff entrance, not part of what
// the public is browsing.
const STAFF_LINK = { href: '/workspace', label: 'Workspace' } as const

const NAV_LINK =
  'rounded-md px-3 py-2 text-sm font-medium text-slate-700 transition ' +
  'hover:bg-slate-100 hover:text-slate-900 ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600 ' +
  'dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-50'

export function SiteHeader() {
  return (
    <header className="border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
      {/* A keyboard user should not have to tab through the whole nav on
          every page to reach the content. */}
      <a
        href="#main"
        className={
          'sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 ' +
          'focus:rounded-md focus:bg-sky-700 focus:px-4 focus:py-2 focus:text-white'
        }
      >
        Skip to content
      </a>

      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-4">
        <Link
          href="/"
          className={
            'rounded-sm text-lg font-bold tracking-tight text-slate-900 ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 dark:text-slate-50'
          }
        >
          EPIRO
        </Link>

        <nav aria-label="Portal" className="-mx-3 flex flex-wrap items-center">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className={NAV_LINK}>
              {item.label}
            </Link>
          ))}
        </nav>

        <Link
          href={STAFF_LINK.href}
          className={`${NAV_LINK} ml-auto border border-slate-300 dark:border-slate-700`}
        >
          {STAFF_LINK.label}
        </Link>
      </div>
    </header>
  )
}

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-slate-200 py-8 dark:border-slate-800">
      <div className="mx-auto max-w-5xl space-y-2 px-4 text-sm text-slate-600 dark:text-slate-400">
        <p>
          Everything published here has been checked against a recorded source and
          approved by someone other than the person who wrote it.
        </p>
        <p>
          A verification state describes how far review has got. It is not a claim
          that a record is true.
        </p>
      </div>
    </footer>
  )
}

/** A page heading with its explanatory standfirst. */
export function PageHeading({
  title,
  description,
}: {
  title: string
  description?: string
}) {
  return (
    <div className="mb-8 space-y-2">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
        {title}
      </h1>
      {description ? (
        <p className="max-w-2xl text-slate-600 dark:text-slate-400">{description}</p>
      ) : null}
    </div>
  )
}

/**
 * Nothing to show, and why.
 *
 * Takes a reason rather than defaulting to "no results", because "nobody has
 * published anything" and "the service is unreachable" must not look the same
 * to a reader.
 */
export function Notice({
  title,
  detail,
}: {
  title: string
  detail?: string
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center dark:border-slate-700">
      <p className="font-medium text-slate-800 dark:text-slate-200">{title}</p>
      {detail ? (
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{detail}</p>
      ) : null}
    </div>
  )
}

/** A responsive grid of cards. */
export function CardGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</div>
  )
}

/**
 * The list routes that paginate.
 *
 * A literal union rather than `string` so typed routes can still check the
 * destination: building a href by concatenating an arbitrary string defeats
 * the check entirely, and a paginated route that does not exist would only
 * show up as a 404 in someone's browser.
 */
export type PaginatedRoute =
  | '/stories'
  | '/evidence'
  | '/questions'
  | '/corrections'
  | '/workspace/intelligence/records'

export function Pagination({
  page,
  totalPages,
  basePath,
  query,
}: {
  page: number
  totalPages: number
  basePath: PaginatedRoute
  /**
   * What the route needs besides the page number.
   *
   * A drill-down page is meaningless without the basis that selected it, so
   * paging through one has to carry that basis along. Dropping it would turn
   * page two of "published evidence" into page two of everything.
   */
  query?: Record<string, string>
}) {
  if (totalPages <= 1) {
    return null
  }

  const link =
    'rounded-md border border-slate-300 px-4 py-2 text-sm font-medium ' +
    'text-slate-700 transition hover:bg-slate-100 ' +
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
    'focus-visible:outline-sky-600 ' +
    'dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800'

  return (
    <nav aria-label="Pagination" className="mt-8 flex items-center justify-between gap-4">
      {page > 1 ? (
        <Link
          href={{ pathname: basePath, query: { ...query, page: page - 1 } }}
          className={link}
          rel="prev"
        >
          ← Previous
        </Link>
      ) : (
        <span />
      )}

      <p className="text-sm text-slate-600 dark:text-slate-400" aria-current="page">
        Page {page} of {totalPages}
      </p>

      {page < totalPages ? (
        <Link
          href={{ pathname: basePath, query: { ...query, page: page + 1 } }}
          className={link}
          rel="next"
        >
          Next →
        </Link>
      ) : (
        <span />
      )}
    </nav>
  )
}
