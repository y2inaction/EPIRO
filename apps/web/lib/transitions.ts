import { APPROVERS, EVIDENCE_VERIFIERS, PUBLISHERS, holds } from '@/lib/session'
import type { Evidence } from '@/lib/workspace'

/**
 * Which workflow actions to offer on an evidence record.
 *
 * This decides what the interface *shows*. It is not the authorisation: the
 * server checks the role and the state again on every call, and is the only
 * thing that can actually refuse one. Getting this wrong shows someone a
 * button that fails, which wastes their time and makes the platform look
 * unreliable — it does not let them do anything they could not otherwise do.
 *
 * The rules mirror app/api/evidence.py. Where they disagree, the server wins.
 */

export type ActionName = 'verify' | 'approve' | 'reject' | 'publish' | 'withdraw'

export interface Action {
  name: ActionName
  label: string
  /** Why this action is the next reasonable step, in a sentence. */
  hint: string
  /** True when the action needs a written reason before it can be sent. */
  requiresReason: boolean
  destructive?: boolean
}

export interface Actor {
  id: string
  role: string | undefined
}

export function availableActions(evidence: Evidence, actor: Actor): Action[] {
  const actions: Action[] = []
  const published = evidence.status === 'published'

  if (
    !published &&
    evidence.verification_status !== 'verified' &&
    holds(actor.role, EVIDENCE_VERIFIERS)
  ) {
    actions.push({
      name: 'verify',
      label: 'Record verification',
      hint: 'Confirm you have checked this record against its source.',
      requiresReason: false,
    })
  }

  if (
    !published &&
    evidence.verification_status === 'verified' &&
    evidence.approval_status !== 'approved' &&
    holds(actor.role, APPROVERS)
  ) {
    actions.push({
      name: 'approve',
      label: 'Approve',
      hint: 'Clear this record for publication. The verifier cannot also approve.',
      requiresReason: false,
    })
  }

  // Rejection stays open while a record is anywhere short of published: an
  // approval can be overturned before it goes out.
  if (!published && holds(actor.role, APPROVERS)) {
    actions.push({
      name: 'reject',
      label: 'Reject',
      hint: 'Send this back with a reason the author can act on.',
      requiresReason: true,
      destructive: true,
    })
  }

  if (!published && evidence.approval_status === 'approved' && holds(actor.role, PUBLISHERS)) {
    actions.push({
      name: 'publish',
      label: 'Publish',
      hint: 'Put this record on the public register.',
      requiresReason: false,
    })
  }

  if (published && holds(actor.role, PUBLISHERS)) {
    actions.push({
      name: 'withdraw',
      label: 'Withdraw',
      hint: 'Retract this from the public register, with a stated reason.',
      requiresReason: true,
      destructive: true,
    })
  }

  return actions
}

/**
 * What a record is waiting for, when the viewer can do nothing about it.
 *
 * Saying "waiting on a verifier" is more use than an empty panel, and it keeps
 * someone from assuming the platform has lost their record.
 */
export function waitingFor(evidence: Evidence): string | null {
  if (evidence.status === 'published') {
    return 'Published. Withdraw it to take it off the public register.'
  }
  if (evidence.status === 'rejected') {
    return 'Rejected. The author revises it and submits it again.'
  }
  if (evidence.status === 'archived') {
    return 'Withdrawn from the public register.'
  }
  if (evidence.verification_status !== 'verified') {
    return 'Waiting to be checked against its source by a verifier.'
  }
  if (evidence.approval_status !== 'approved') {
    return 'Verified. Waiting on an approver, who must be someone other than the verifier.'
  }
  return 'Approved. Waiting on a publisher.'
}
