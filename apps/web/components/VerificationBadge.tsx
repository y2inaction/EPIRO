import { verificationLabel } from '@/lib/format'

const TONE_CLASSES: Record<string, string> = {
  checked:
    'bg-emerald-50 text-emerald-900 ring-emerald-600/20 ' +
    'dark:bg-emerald-950 dark:text-emerald-100 dark:ring-emerald-400/30',
  pending:
    'bg-amber-50 text-amber-900 ring-amber-600/20 ' +
    'dark:bg-amber-950 dark:text-amber-100 dark:ring-amber-400/30',
  disputed:
    'bg-rose-50 text-rose-900 ring-rose-600/20 ' +
    'dark:bg-rose-950 dark:text-rose-100 dark:ring-rose-400/30',
}

/**
 * The verification state of an evidence record.
 *
 * Carries its meaning as visible text rather than only as a colour, because a
 * coloured pill reading "Verified" invites a reader to take it as "true" —
 * which is exactly what spec section 11 forbids the platform from claiming.
 */
export function VerificationBadge({
  status,
  withMeaning = false,
}: {
  status: string
  withMeaning?: boolean
}) {
  const { label, meaning, tone } = verificationLabel(status)

  return (
    <span className="inline-flex flex-col gap-1">
      <span
        className={
          'inline-flex w-fit items-center rounded-full px-2.5 py-0.5 ' +
          'text-xs font-medium ring-1 ring-inset ' +
          (TONE_CLASSES[tone] ?? TONE_CLASSES.pending)
        }
      >
        {label}
      </span>
      {withMeaning ? (
        <span className="text-xs text-slate-600 dark:text-slate-400">{meaning}</span>
      ) : null}
    </span>
  )
}
