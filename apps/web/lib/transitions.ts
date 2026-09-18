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

// --- Stories ---------------------------------------------------------------

/** Editorial sign-off, kept separate from publishing so two people are needed. */
export const STORY_APPROVERS = ['approver', 'executive', 'editor']
export const CONTENT_AUTHORS = ['content_manager', 'editor', 'translator']

export type StoryActionName =
  | 'submit'
  | 'approve'
  | 'reject'
  | 'publish'
  | 'withdraw'

export interface StoryAction {
  name: StoryActionName
  label: string
  hint: string
  requiresReason: boolean
  destructive?: boolean
}

export interface StoryLike {
  status: string
}

export function storyActions(story: StoryLike, role: string | undefined): StoryAction[] {
  const actions: StoryAction[] = []

  if (
    (story.status === 'draft' || story.status === 'rejected') &&
    holds(role, CONTENT_AUTHORS)
  ) {
    actions.push({
      name: 'submit',
      label: 'Submit for review',
      hint: 'Put this in front of a reviewer.',
      requiresReason: false,
    })
  }

  if (story.status === 'in_review' && holds(role, STORY_APPROVERS)) {
    actions.push({
      name: 'approve',
      label: 'Approve',
      hint: 'Sign this off. Someone else publishes it, and you cannot be its author.',
      requiresReason: false,
    })
  }

  if (
    (story.status === 'in_review' || story.status === 'approved') &&
    holds(role, STORY_APPROVERS)
  ) {
    actions.push({
      name: 'reject',
      label: 'Send back',
      hint: 'Return this with a reason. Any existing approval is cleared.',
      requiresReason: true,
      destructive: true,
    })
  }

  if (story.status === 'approved' && holds(role, PUBLISHERS)) {
    actions.push({
      name: 'publish',
      label: 'Publish',
      hint: 'Release this publicly. You cannot be the person who approved it.',
      requiresReason: false,
    })
  }

  if (story.status === 'published' && holds(role, PUBLISHERS)) {
    actions.push({
      name: 'withdraw',
      label: 'Withdraw',
      hint: 'Retract this, with a stated reason. It also leaves the featured set.',
      requiresReason: true,
      destructive: true,
    })
  }

  return actions
}

export function storyWaitingFor(story: StoryLike): string {
  switch (story.status) {
    case 'draft':
      return 'A draft. The author submits it when it is ready.'
    case 'in_review':
      return 'Waiting on a reviewer, who cannot be its author.'
    case 'approved':
      return 'Approved. Waiting on a publisher, who cannot be the approver.'
    case 'rejected':
      return 'Sent back. The author revises it and submits it again.'
    case 'published':
      return 'Published.'
    case 'archived':
      return 'Withdrawn from the public portal.'
    default:
      return 'In the editorial workflow.'
  }
}

// --- Questions -------------------------------------------------------------

export const QUESTION_RESPONDERS = [
  'researcher',
  'content_manager',
  'editor',
  'evidence_manager',
]

export type QuestionActionName =
  | 'triage'
  | 'respond'
  | 'approve'
  | 'reject'
  | 'publish'

export interface QuestionAction {
  name: QuestionActionName
  label: string
  hint: string
  requiresReason: boolean
  destructive?: boolean
}

export interface QuestionLike {
  status: string
  response: string | null
}

/** States in which an answer can still be drafted or rewritten. */
const RESPONDABLE = ['triaged', 'researching', 'verified', 'response_drafted']

export function questionActions(
  question: QuestionLike,
  role: string | undefined,
): QuestionAction[] {
  const actions: QuestionAction[] = []

  if (question.status === 'new' && holds(role, QUESTION_RESPONDERS)) {
    actions.push({
      name: 'triage',
      label: 'Claim this question',
      hint: 'Assign it to your organisation so it can be answered.',
      requiresReason: false,
    })
  }

  if (RESPONDABLE.includes(question.status) && holds(role, QUESTION_RESPONDERS)) {
    actions.push({
      name: 'respond',
      label: question.response ? 'Rewrite the answer' : 'Draft an answer',
      hint: 'Write the answer that will be published if it is approved.',
      requiresReason: true,
    })
  }

  if (question.status === 'response_drafted' && holds(role, APPROVERS)) {
    actions.push({
      name: 'approve',
      label: 'Approve the answer',
      hint: 'You cannot approve an answer you drafted yourself.',
      requiresReason: false,
    })
  }

  if (
    (question.status === 'response_drafted' || question.status === 'approved') &&
    holds(role, APPROVERS)
  ) {
    actions.push({
      name: 'reject',
      label: 'Send back',
      hint: 'Return this for more research, with a reason.',
      requiresReason: true,
      destructive: true,
    })
  }

  if (question.status === 'approved' && holds(role, PUBLISHERS)) {
    actions.push({
      name: 'publish',
      label: 'Publish the answer',
      hint: 'Put the question and its answer on the public portal.',
      requiresReason: false,
    })
  }

  return actions
}

export function questionWaitingFor(question: QuestionLike): string {
  switch (question.status) {
    case 'new':
      return 'Nobody has claimed this yet.'
    case 'triaged':
    case 'researching':
      return 'Claimed. Waiting for someone to draft an answer.'
    case 'response_drafted':
      return 'An answer is drafted. Waiting on an approver, who cannot have drafted it.'
    case 'approved':
      return 'Approved. Waiting on a publisher, who cannot be the approver.'
    case 'published':
      return 'Published on the public portal.'
    case 'closed':
      return 'Closed. No further answer will be given.'
    default:
      return 'In the question workflow.'
  }
}
