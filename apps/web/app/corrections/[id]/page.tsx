import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { FindingBadge } from '@/components/VerificationBadge'
import { getCorrection } from '@/lib/api'
import { excerpt, findingLabel, formatDate, isoDate } from '@/lib/format'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>
}): Promise<Metadata> {
  const { id } = await params
  const result = await getCorrection(id)

  if (!result.ok) {
    return { title: 'Correction' }
  }

  // The title leads with the finding, not the claim. A page titled only with
  // the false claim is that claim repeated under the platform's name, in every
  // share preview and search result that never shows the body.
  const { label } = findingLabel(result.value.finding)
  return {
    title: `${label}: ${excerpt(result.value.claim, 90)}`,
    description: result.value.response ?? result.value.assessment ?? undefined,
  }
}

function Paragraphs({ text }: { text: string }) {
  return (
    <>
      {text
        .split(/\n{2,}/)
        .map((paragraph) => paragraph.trim())
        .filter(Boolean)
        .map((paragraph, index) => (
          // Paragraphs have no identity of their own and the list never
          // reorders, so the index is the position.
          <p key={index}>{paragraph}</p>
        ))}
    </>
  )
}

export default async function CorrectionPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const result = await getCorrection(id)

  // A withdrawn or unpublished correction is 404 from the API, and the portal
  // renders it the same way. This matters more here than elsewhere: a
  // correction that has been taken back must not still be readable.
  if (!result.ok && result.status === 404) {
    notFound()
  }

  if (!result.ok) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center dark:border-slate-700">
        <p className="font-medium text-slate-800 dark:text-slate-200">
          This correction is temporarily unavailable
        </p>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{result.message}</p>
      </div>
    )
  }

  const correction = result.value
  const published = formatDate(correction.published_at)
  const observed = formatDate(correction.first_observed)

  return (
    <article className="mx-auto max-w-2xl">
      <nav aria-label="Breadcrumb" className="mb-6">
        <Link
          href="/corrections"
          className="rounded-sm text-sm text-slate-600 underline underline-offset-4 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:text-slate-400 dark:hover:text-slate-100"
        >
          ← All corrections
        </Link>
      </nav>

      <header className="space-y-4 border-b border-slate-200 pb-6 dark:border-slate-800">
        <FindingBadge finding={correction.finding} withMeaning />

        {/* Marked up as a quotation, and introduced as one, so that the claim
            is never read as the publishing body's own statement. */}
        <h1 className="text-2xl font-bold leading-snug tracking-tight text-slate-900 dark:text-slate-50">
          <span className="block text-sm font-medium uppercase tracking-wide text-slate-600 dark:text-slate-400">
            The claim that was circulating
          </span>
          <blockquote className="mt-2">“{correction.claim}”</blockquote>
        </h1>

        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-600 dark:text-slate-400">
          {correction.organisation ? (
            <span>Assessed by {correction.organisation.name}</span>
          ) : null}
          {correction.organisation && published ? <span aria-hidden="true">·</span> : null}
          {published ? (
            <time dateTime={isoDate(correction.published_at)}>Published {published}</time>
          ) : null}
        </div>

        {correction.source || observed ? (
          <p className="text-sm text-slate-600 dark:text-slate-400">
            {correction.source ? <>Seen on {correction.source}</> : null}
            {correction.source && observed ? ', ' : null}
            {observed ? <>first observed {observed}</> : null}.
          </p>
        ) : null}
      </header>

      {correction.response ? (
        <section className="mt-8" aria-labelledby="response">
          <h2
            id="response"
            className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400"
          >
            What the body says
          </h2>
          <div className="mt-3 space-y-4 text-lg leading-relaxed text-slate-800 dark:text-slate-200">
            <Paragraphs text={correction.response} />
          </div>
        </section>
      ) : null}

      {correction.assessment ? (
        <section className="mt-8" aria-labelledby="assessment">
          <h2
            id="assessment"
            className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400"
          >
            How this was established
          </h2>
          <div className="mt-3 space-y-4 leading-relaxed text-slate-700 dark:text-slate-300">
            <Paragraphs text={correction.assessment} />
          </div>
        </section>
      ) : null}

      {correction.evidence_reference ? (
        <aside className="mt-10 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            The evidence this finding rests on
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
            A correction you cannot check is just another claim. This one was
            approved against a recorded piece of evidence, and you can read that
            record and the state of its verification directly.
          </p>
          <Link
            href={`/evidence/${correction.evidence_reference}`}
            className="mt-3 inline-block rounded-md bg-slate-900 px-4 py-2 font-mono text-sm text-white transition hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          >
            {correction.evidence_reference}
          </Link>
        </aside>
      ) : null}
    </article>
  )
}
