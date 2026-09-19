'use server'

import { revalidatePath } from 'next/cache'

import type { DecisionAction } from '@/lib/decisions'
import { acceptAction, completeAction, dropAction, startAction } from '@/lib/workspace'
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
