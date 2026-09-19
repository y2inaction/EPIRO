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
