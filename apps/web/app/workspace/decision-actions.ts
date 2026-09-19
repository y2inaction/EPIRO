'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'

import type { DecisionAction } from '@/lib/decisions'
import { parseOrigin } from '@/lib/decisions'
import {
  acceptAction,
  completeAction,
  dropAction,
  raiseAction,
  startAction,
} from '@/lib/workspace'
import type { TransitionState } from '@/app/workspace/content-actions'

const DONE: Record<DecisionAction, string> = {
  accept: 'Accepted. It is on the register as agreed work.',
  start: 'Recorded as under way.',
  complete: 'Closed, with your account of what happened.',
  drop: 'Recorded as decided against, with your reasoning kept.',
}

/**
 * Move an action along, or say why it could not move.
 *
 * The outcome is checked here before the round trip so a person is told
 * sooner, and checked again on the server because this check is a courtesy
 * and that one is the rule.
 */
export async function applyDecision(
  _state: TransitionState,
  formData: FormData,
): Promise<TransitionState> {
  const id = String(formData.get('action_id') ?? '')
  const move = String(formData.get('move') ?? '') as DecisionAction
  const outcome = String(formData.get('outcome') ?? '').trim()

  if ((move === 'complete' || move === 'drop') && !outcome) {
    return { error: 'Write what happened. A status that changed with no account explains nothing later.' }
  }

  const result =
    move === 'accept'
      ? await acceptAction(id)
      : move === 'start'
        ? await startAction(id)
        : move === 'complete'
          ? await completeAction(id, outcome)
          : await dropAction(id, outcome)

  if (!result.ok) {
    // The API's own message says which rule was broken or which role was
    // needed, which is more use than anything this layer could invent.
    return { error: result.message }
  }

  revalidatePath(`/workspace/actions/${id}`)
  revalidatePath('/workspace/actions')
  return { done: DONE[move] }
}


/**
 * Raise an action against something the organisation already holds.
 *
 * The origin is required and is checked again on the server, which also
 * confirms the cited record exists inside the caller's organisations. This
 * check only spares a round trip.
 */
export async function raiseDecision(
  _state: TransitionState,
  formData: FormData,
): Promise<TransitionState> {
  const origin = parseOrigin(String(formData.get('origin') ?? ''))
  const title = String(formData.get('title') ?? '').trim()
  const rationale = String(formData.get('rationale') ?? '').trim()
  const dueDate = String(formData.get('due_date') ?? '').trim()

  if (!origin) {
    return { error: 'Choose what prompted this. An action nobody can trace back to a finding is a wish list.' }
  }
  if (!title || !rationale) {
    return { error: 'A title and the reasoning are both needed. The reasoning is the part nobody can reconstruct later.' }
  }

  const result = await raiseAction({
    organisation_id: String(formData.get('organisation_id') ?? ''),
    title,
    rationale,
    origin_type: origin.originType,
    origin_id: origin.originId,
    owner_id: String(formData.get('owner_id') ?? ''),
    due_date: dueDate || null,
  })

  if (!result.ok) {
    return { error: result.message }
  }

  revalidatePath('/workspace/actions')
  redirect(`/workspace/actions/${result.value.id}`)
}
