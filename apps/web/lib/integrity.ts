/**
 * What a person may do to an integrity signal, and what to call it.
 *
 * Pure, so the lifecycle the interface offers can be checked against the one
 * the server enforces without rendering anything. Keeping them in step is
 * about honesty rather than safety — the server refuses an illegal move
 * either way, and offering a button that always fails wastes somebody's time.
 *
 * Mirrors app/api/integrity.py and app/services/integrity.py.
 */

export interface Signal {
  id: string
  organisation_id: string
  claim: string
  source: string | null
  circulation: string | null
  first_observed: string | null
  language: string
  status: string
  priority: string
  finding: string | null
  assessment: string | null
  impact: string | null
  response: string | null
  evidence_id: string | null
  published_at: string | null
  version: number
  created_at: string
  updated_at: string
}

export type SignalMove = 'assess' | 'respond' | 'approve' | 'reject' | 'publish' | 'withdraw'

export interface SignalOffer {
  name: SignalMove
  label: string
  hint: string
  /** The free-text field this move requires, if any. */
  field?: { name: string; label: string; rows: number }
  /** Whether it also needs a finding chosen. */
  needsFinding?: boolean
  /** Whether it offers an evidence citation. */
  offersEvidence?: boolean
  destructive?: boolean
}

const ASSESS: SignalOffer = {
  name: 'assess',
  label: 'Record what you found',
  hint: 'The finding and the reasoning are written together. A verdict with no reasoning is an unexplainable one, and the API will not accept it.',
  field: { name: 'assessment', label: 'Why you concluded that', rows: 4 },
  needsFinding: true,
  offersEvidence: true,
}

const RESPOND: SignalOffer = {
  name: 'respond',
  label: 'Draft the correction',
  hint: 'What the body intends to put out. It still needs approval and then publication by other people.',
  field: { name: 'response', label: 'The correction', rows: 4 },
}

const APPROVE: SignalOffer = {
  name: 'approve',
  label: 'Sign off the finding',
  hint: 'Refused unless the finding cites evidence this organisation has itself approved, and unless you are somebody other than the assessor.',
  field: { name: 'comments', label: 'Comments (optional)', rows: 2 },
}

const REJECT: SignalOffer = {
  name: 'reject',
  label: 'Send it back',
  hint: 'Returns it for more work, with your reason on the approval trail.',
  field: { name: 'comments', label: 'Why it is going back', rows: 3 },
  destructive: true,
}

const PUBLISH: SignalOffer = {
  name: 'publish',
  label: 'Publish the correction',
  hint: 'Puts it on the public portal. Refused if you are the person who approved it.',
}

const WITHDRAW: SignalOffer = {
  name: 'withdraw',
  label: 'Withdraw it',
  hint: 'Retracted rather than deleted: the record stays and states why what was published no longer stands.',
  field: { name: 'reason', label: 'Why it is being withdrawn', rows: 3 },
  destructive: true,
}

/**
 * What is offered from each state.
 *
 * `respond` appears in three states because the API allows drafting the
 * correction before or after the finding is signed off — but never after
 * publication, when changing it would rewrite what the public was told.
 */
const OFFERED: Record<string, SignalOffer[]> = {
  new: [ASSESS, RESPOND],
  assessing: [ASSESS, RESPOND],
  assessed: [ASSESS, RESPOND, APPROVE, REJECT],
  approved: [RESPOND, REJECT, PUBLISH],
  published: [WITHDRAW],
  withdrawn: [],
  closed: [],
}

export function offersFor(status: string): SignalOffer[] {
  return OFFERED[status] ?? []
}

/**
 * What the signal is waiting for.
 *
 * Never empty. A screen showing no buttons and no explanation leaves a reader
 * unable to tell a finished record from a permission they lack.
 */
export function waitingFor(signal: Signal): string {
  switch (signal.status) {
    case 'new':
    case 'assessing':
      return 'Nobody has recorded a finding yet.'
    case 'assessed':
      return signal.evidence_id || signal.finding === 'unresolved'
        ? 'Waiting for somebody other than the assessor to sign the finding off.'
        : 'Waiting for sign-off, which will be refused until the finding cites approved evidence. "Unresolved" is the one finding exempt, because it asserts nothing to source.'
    case 'approved':
      return signal.response
        ? 'Waiting for somebody other than the approver to publish it.'
        : 'Signed off. A correction has to be drafted before it can be published.'
    case 'published':
      return 'On the public portal.'
    case 'withdrawn':
      return 'Retracted. The record stays, stating why what was published no longer stands.'
    case 'closed':
      return 'Closed.'
    default:
      return 'This state is not one the interface knows about.'
  }
}

/** The findings the API accepts, in the order they are offered. */
export const FINDINGS = [
  'accurate',
  'misleading',
  'out_of_context',
  'false',
  'unsubstantiated',
  'unresolved',
] as const
