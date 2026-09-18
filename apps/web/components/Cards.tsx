import Link from 'next/link'

import { FindingBadge, VerificationBadge } from '@/components/VerificationBadge'
import type {
  PublicCorrection,
  PublicEvidence,
  PublicQuestion,
  PublicStory,
} from '@/lib/api'
import { excerpt, formatCount, formatDate, isoDate } from '@/lib/format'

const CARD =
  'group flex h-full flex-col gap-3 rounded-xl border border-slate-200 bg-white p-5 ' +
  'transition hover:border-slate-300 hover:shadow-sm ' +
  'dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700'

const TITLE_LINK =
  'rounded-sm text-lg font-semibold leading-snug text-slate-900 ' +
  'underline-offset-4 group-hover:underline ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-sky-600 dark:text-slate-50'

const META = 'text-xs text-slate-600 dark:text-slate-400'

/** The publishing body, the date, and anything else that sets context. */
function Meta({ children }: { children: React.ReactNode }) {
  return <div className={`flex flex-wrap items-center gap-x-2 gap-y-1 ${META}`}>{children}</div>
}

function Dot() {
  return <span aria-hidden="true">·</span>
}

export function StoryCard({ story }: { story: PublicStory }) {
  const published = formatDate(story.published_date)

  return (
    <article className={CARD}>
      <Meta>
        {story.organisation ? <span>{story.organisation.name}</span> : null}
        {story.organisation && published ? <Dot /> : null}
        {published ? (
          <time dateTime={isoDate(story.published_date)}>{published}</time>
        ) : null}
        {story.featured ? (
          <>
            <Dot />
            <span className="font-medium text-sky-700 dark:text-sky-400">Featured</span>
          </>
        ) : null}
      </Meta>

      <h3>
        {/* The whole card is not a link: a nested-link card is a keyboard and
            screen-reader trap. The heading is the one target. */}
        <Link href={`/stories/${story.id}`} className={TITLE_LINK}>
          {story.title}
        </Link>
      </h3>

      {story.headline ? (
        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
          {story.headline}
        </p>
      ) : null}

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
        {excerpt(story.summary ?? story.body)}
      </p>

      {story.evidence_reference ? (
        <p className={`mt-auto pt-2 ${META}`}>
          Evidence{' '}
          <Link
            href={`/evidence/${story.evidence_reference}`}
            className="font-mono underline underline-offset-2 hover:text-slate-900 dark:hover:text-slate-100"
          >
            {story.evidence_reference}
          </Link>
        </p>
      ) : null}
    </article>
  )
}

export function EvidenceCard({ record }: { record: PublicEvidence }) {
  const recorded = formatDate(record.evidence_date)
  const beneficiaries = formatCount(record.beneficiaries)

  return (
    <article className={CARD}>
      <Meta>
        <Link
          href={`/evidence/${record.reference}`}
          className="font-mono font-medium text-slate-700 underline underline-offset-2 dark:text-slate-300"
        >
          {record.reference}
        </Link>
        {record.organisation ? (
          <>
            <Dot />
            <span>{record.organisation.name}</span>
          </>
        ) : null}
        {recorded ? (
          <>
            <Dot />
            <time dateTime={isoDate(record.evidence_date)}>{recorded}</time>
          </>
        ) : null}
      </Meta>

      <h3>
        <Link href={`/evidence/${record.reference}`} className={TITLE_LINK}>
          {record.title}
        </Link>
      </h3>

      {record.description ? (
        <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
          {excerpt(record.description)}
        </p>
      ) : null}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-2">
        <VerificationBadge status={record.verification_status} />
        {beneficiaries ? (
          <span className={META}>{beneficiaries} people reached</span>
        ) : null}
      </div>
    </article>
  )
}

/**
 * A published finding about a claim that was circulating.
 *
 * The claim is shown as reported speech and the finding sits beside it, so a
 * reader skimming the card cannot come away having read the false claim as the
 * body's own statement. Repeating a claim in order to correct it is the whole
 * difficulty of this page; putting the verdict next to it is the least a
 * summary card can do about that.
 */
export function CorrectionCard({ correction }: { correction: PublicCorrection }) {
  const published = formatDate(correction.published_at)

  return (
    <article className={CARD}>
      <Meta>
        {correction.organisation ? (
          <span>Assessed by {correction.organisation.name}</span>
        ) : null}
        {correction.organisation && published ? <Dot /> : null}
        {published ? (
          <time dateTime={isoDate(correction.published_at)}>{published}</time>
        ) : null}
        {correction.source ? (
          <>
            <Dot />
            <span>Seen on {correction.source}</span>
          </>
        ) : null}
      </Meta>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="flex-1 text-base font-semibold leading-snug text-slate-900 dark:text-slate-50">
          <Link href={`/corrections/${correction.id}`} className={TITLE_LINK}>
            <span className="text-sm font-normal text-slate-600 dark:text-slate-400">
              Claim:{' '}
            </span>
            “{excerpt(correction.claim, 160)}”
          </Link>
        </h3>
        <FindingBadge finding={correction.finding} />
      </div>

      {correction.response ? (
        <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
          {excerpt(correction.response, 260)}
        </p>
      ) : null}

      {correction.evidence_reference ? (
        <p className={`mt-auto pt-2 ${META}`}>
          Assessed against{' '}
          <Link
            href={`/evidence/${correction.evidence_reference}`}
            className="font-mono underline underline-offset-2 hover:text-slate-900 dark:hover:text-slate-100"
          >
            {correction.evidence_reference}
          </Link>
        </p>
      ) : null}
    </article>
  )
}

export function QuestionCard({ question }: { question: PublicQuestion }) {
  const answered = formatDate(question.response_date)

  return (
    <article className={CARD}>
      <Meta>
        {question.category ? <span className="capitalize">{question.category}</span> : null}
        {question.category && question.organisation ? <Dot /> : null}
        {question.organisation ? <span>Answered by {question.organisation.name}</span> : null}
        {answered ? (
          <>
            <Dot />
            <time dateTime={isoDate(question.response_date)}>{answered}</time>
          </>
        ) : null}
      </Meta>

      <h3 className="text-base font-semibold leading-snug text-slate-900 dark:text-slate-50">
        {question.question_text}
      </h3>

      {question.response ? (
        <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
          {excerpt(question.response, 260)}
        </p>
      ) : null}
    </article>
  )
}
