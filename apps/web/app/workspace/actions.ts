'use server'

import { revalidatePath } from 'next/cache'

import type { ActionName } from '@/lib/transitions'
import {
  approveEvidence,
  publishEvidence,
  rejectEvidence,
  verifyEvidence,
  withdrawEvidence,
} from '@/lib/workspace'

export interface TransitionState {
  error?: string
  done?: string
}

/**
 * Apply a workflow transition to an evidence record.
 *
 * One action for all five transitions, because they share everything that
 * matters: the same validation of the reason, the same handling of a refusal,
 * and the same need to re-read the record afterwards. The server decides
 * whether the transition is allowed; this only carries the request and reports
 * back what happened.
 *
 * A refusal is shown with the API's own wording, which says which role was
 * needed or which rule the transition broke. Replacing it with a generic
 * "something went wrong" would hide the one piece of information the person
 * needs to act.
 */
export async function applyTransition(
  _state: TransitionState,
  formData: FormData,
): Promise<TransitionState> {
  const id = String(formData.get('evidence_id') ?? '')
  const action = String(formData.get('action') ?? '') as ActionName
  const reason = String(formData.get('reason') ?? '').trim()
  const changesRequested = formData.get('changes_requested') === 'on'

  if (!id) {
    return { error: 'No record was named.' }
  }

  if ((action === 'reject' || action === 'withdraw') && !reason) {
    // Checked here as well as on the server so the person is told before the
    // round trip. A rejection with no stated reason gives the author nothing
    // to act on, which is why the API requires one too.
    return { error: 'Give a reason. The author needs to know what to change.' }
  }

  let result
  switch (action) {
    case 'verify':
      result = await verifyEvidence(id, reason || undefined)
      break
    case 'approve':
      result = await approveEvidence(id, reason || undefined)
      break
    case 'reject':
      result = await rejectEvidence(id, reason, changesRequested)
      break
    case 'publish':
      result = await publishEvidence(id)
      break
    case 'withdraw':
      result = await withdrawEvidence(id, reason)
      break
    default:
      return { error: 'That is not an action on this record.' }
  }

  if (!result.ok) {
    return { error: result.message }
  }

  revalidatePath(`/workspace/evidence/${id}`)
  revalidatePath('/workspace')

  return { done: DONE_MESSAGES[action] }
}

const DONE_MESSAGES: Record<ActionName, string> = {
  verify: 'Verification recorded.',
  approve: 'Approved. It can now be published by someone else.',
  reject: 'Sent back with your reason. It is on the approval trail.',
  publish: 'Published to the public register.',
  withdraw: 'Withdrawn. The record stays, marked as retracted.',
}
