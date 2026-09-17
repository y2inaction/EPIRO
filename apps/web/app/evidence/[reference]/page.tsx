import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { VerificationBadge } from '@/components/VerificationBadge'
import { getEvidence } from '@/lib/api'
import { formatCount, formatDate, isoDate } from '@/lib/format'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ reference: string }>
}): Promise<Metadata> {
  const { reference } = await params
  const result = await getEvidence(reference)

  if (!result.ok) {
    return { title: 'Evidence record' }
  }

  return {
    title: `${result.value.reference} — ${result.value.title}`,
    description: result.value.description ?? undefined,
  }
}

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="border-t border-slate-200 py-4 dark:border-slate-800">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
        {label}
      </dt>
      <dd className="mt-1 text-slate-800 dark:text-slate-200">{children}</dd>
    </div>
  )
}

export default async function EvidenceRecordPage({
  params,
}: {
  params: Promise<{ reference: string }>
}) {
  const { reference } = await params
  const result = await getEvidence(reference)

  if (!result.ok && result.status === 404) {
    notFound()
  }

  if (!result.ok) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center dark:border-slate-700">
        <p className="font-medium text-slate-800 dark:text-slate-200">
          This record is temporarily unavailable
        </p>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{result.message}</p>
      </div>
    )
  }

  const record = result.value
  const recorded = formatDate(record.evidence_date)
  const beneficiaries = formatCount(record.beneficiaries)

  return (
    <article className="mx-auto max-w-2xl">
      <nav aria-label="Breadcrumb" className="mb-6">
        <Link
          href="/evidence"
          className="rounded-sm text-sm text-slate-600 underline underline-offset-4 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:text-slate-400 dark:hover:text-slate-100"
        >
          ← Evidence register
        </Link>
      </nav>

      <header className="space-y-3">
        <p className="font-mono text-sm text-slate-600 dark:text-slate-400">
          {record.reference}
        </p>
        <h1 className="text-3xl font-bold leading-tight tracking-tight text-slate-900 dark:text-slate-50">
          {record.title}
        </h1>
        <VerificationBadge status={record.verification_status} withMeaning />
      </header>

      {record.description ? (
        <p className="mt-6 leading-relaxed text-slate-800 dark:text-slate-200">
          {record.description}
        </p>
      ) : null}

      <dl className="mt-8">
        {record.organisation ? (
          <Field label="Recorded by">{record.organisation.name}</Field>
        ) : null}

        {recorded ? (
          <Field label="Date of the evidence">
            <time dateTime={isoDate(record.evidence_date)}>{recorded}</time>
          </Field>
        ) : null}

        {record.outcome ? <Field label="Outcome">{record.outcome}</Field> : null}

        {beneficiaries ? (
          <Field label="People reached">{beneficiaries}</Field>
        ) : null}

        {record.tags.length > 0 ? (
          <Field label="Tags">
            <ul className="flex flex-wrap gap-2">
              {record.tags.map((tag) => (
                <li
                  key={tag}
                  className="rounded-full bg-slate-100 px-2.5 py-0.5 text-sm dark:bg-slate-800"
                >
                  {tag}
                </li>
              ))}
            </ul>
          </Field>
        ) : null}

        {record.document_url ? (
          <Field label="Supporting document">
            <a
              href={record.document_url}
              rel="noopener noreferrer nofollow"
              target="_blank"
              className="break-all underline underline-offset-4 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:hover:text-white"
            >
              {record.document_url}
            </a>
            <span className="mt-1 block text-xs text-slate-600 dark:text-slate-400">
              This link leaves the portal and is not hosted here.
            </span>
          </Field>
        ) : null}
      </dl>

      <p className="mt-8 rounded-lg bg-slate-100 p-4 text-sm leading-relaxed text-slate-700 dark:bg-slate-900 dark:text-slate-300">
        Cite this record as{' '}
        <span className="font-mono font-medium">{record.reference}</span>. The
        reference is permanent and will keep pointing at this record.
      </p>
    </article>
  )
}
