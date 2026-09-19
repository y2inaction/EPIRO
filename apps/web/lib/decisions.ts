/**
 * What a person may do to an action, and what to call it.
 *
 * Pure, so the lifecycle the interface offers can be tested against the one
 * the server enforces without rendering anything. Keeping them in step
 * matters for honesty rather than safety: the server refuses an illegal move
 * either way, and offering a button that always fails wastes somebody's time
 * and makes the system look broken.
 */

export type DecisionAction = 'accept' | 'start' | 'complete' | 'drop'

export interface DecisionOffer {
  name: DecisionAction
  label: string
  hint: string
  /** Whether the server will refuse this without a written outcome. */
  needsOutcome: boolean
  destructive?: boolean
}

const ACCEPT: DecisionOffer = {
  name: 'accept',
  label: 'Accept it',
  hint: 'Agree that this will be done. It stays open until somebody starts it.',
  needsOutcome: false,
}

const START: DecisionOffer = {
  name: 'start',
  label: 'Start work',
  hint: 'Record that work has begun.',
  needsOutcome: false,
}

const COMPLETE: DecisionOffer = {
  name: 'complete',
  label: 'Record it as done',
  hint: 'Say what actually happened. The status is not the useful part; the account is.',
  needsOutcome: true,
}

const DROP: DecisionOffer = {
  name: 'drop',
  label: 'Decide not to do it',
  hint: 'Kept with your reasoning rather than deleted. Why nothing happened is usually the part worth having.',
  needsOutcome: true,
  destructive: true,
}

/** Mirrors the lifecycle in app/services/actions.py. */
const OFFERED: Record<string, DecisionOffer[]> = {
  proposed: [ACCEPT, DROP],
  accepted: [START, DROP],
  in_progress: [COMPLETE, DROP],
  done: [],
  dropped: [],
}

export function offersFor(status: string): DecisionOffer[] {
  return OFFERED[status] ?? []
}

/**
 * What the action is waiting for, when there is nothing to offer.
 *
 * A screen that simply shows no buttons leaves a reader wondering whether
 * they lack a permission or the record is finished. Those are different
 * facts.
 */
export function waitingFor(status: string, overdue: boolean): string {
  if (status === 'done') {
    return 'Carried out. Closed decisions are not reopened — a decision revisited is a new one.'
  }
  if (status === 'dropped') {
    return 'Decided against, with the reasoning kept. Raise a new action if it comes back.'
  }
  if (overdue) {
    return 'Past its date and still open.'
  }
  return 'Open.'
}


/**
 * What an action can be raised from, and where to find the candidates.
 *
 * The intelligence drill-down already lists every record of a measure,
 * scoped and filtered exactly as the dashboard is, so the picker reuses it
 * rather than adding a second way to enumerate the same rows.
 *
 * `drill_finding` is missing on purpose: findings are not an intelligence
 * measure, so there is no list to draw from here. An action can still be
 * raised against one through the API.
 */
export const ORIGIN_SOURCES = [
  { originType: 'integrity_signal', measure: 'integrity_signals', label: 'Integrity signal' },
  { originType: 'scenario', measure: 'scenarios', label: 'Readiness scenario' },
  { originType: 'evidence', measure: 'evidence', label: 'Evidence record' },
] as const

/**
 * Split the picker's value back into a type and an id.
 *
 * One select rather than two linked ones, so the form needs no scripting.
 * Returns null for anything malformed rather than guessing — an action with
 * a mis-parsed origin would cite the wrong record, which is worse than a
 * refusal.
 */
export function parseOrigin(value: string): { originType: string; originId: string } | null {
  const split = value.indexOf(':')
  if (split <= 0) {
    return null
  }

  const originType = value.slice(0, split)
  const originId = value.slice(split + 1)

  if (!originId || !ORIGIN_SOURCES.some((s) => s.originType === originType)) {
    return null
  }
  return { originType, originId }
}
