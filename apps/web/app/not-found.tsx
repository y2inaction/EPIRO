import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="mx-auto max-w-lg py-16 text-center">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
        Not found
      </h1>
      <p className="mt-3 leading-relaxed text-slate-600 dark:text-slate-400">
        There is nothing published at this address. It may never have existed, or
        it may have been withdrawn.
      </p>
      <Link
        href="/"
        className="mt-6 inline-block rounded-md bg-slate-900 px-5 py-2 font-medium text-white transition hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
      >
        Back to the portal
      </Link>
    </div>
  )
}
