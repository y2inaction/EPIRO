'use server'

import { revalidatePath } from 'next/cache'

import type { TransitionState } from '@/app/workspace/content-actions'
import type { SignalMove } from '@/lib/integrity'
import { moveSignal } from '@/lib/workspace'

const DONE: Record<SignalMove, string> = {
  assess: 'Finding recorded. Somebody else signs it off.',
  respond: 'Correction drafted. It still needs approval and publication.',
  approve: 'Signed off. Somebody else publishes it.',
  reject: 'Sent back, with your reason on the approval trail.',
  publish: 'Published to the public portal.',
  withdraw: 'Withdrawn. The record stays, marked as retracted.',
}

/** The free-text a move will not proceed without. */
const REQUIRED: Partial<Record<SignalMove, string>> = {
  assess: 'assessment',
  respond: 'response',
  reject: 'comments',
  withdraw: 'reason',
}

/**
 * Apply a move to a signal, or say why it could not be applied.
 *
 * The required text is checked here so a person is told sooner, and again on
 * the server because that is where the rule lives. The refusals that matter
 * most — a finding with no approved evidence behind it, an approver
 * publishing their own sign-off — are only enforceable there, and their
 * wording is passed through unchanged.
 */
export async function applySignalMove(
  _state: TransitionState,
  formData: FormData,
): Promise<TransitionState> {
  const id = String(formData.get('signal_id') ?? '')
  const move = String(formData.get('move') ?? '') as SignalMove

  const needed = REQUIRED[move]
  const text = String(formData.get(needed ?? '') ?? '').trim()
  if (needed && !text) {
    return { error: 'This needs writing before it can be recorded.' }
  }

  const body: Record<string, unknown> = {}
  if (needed) {
    body[needed] = text
  }
  if (move === 'assess') {
    body.finding = String(formData.get('finding') ?? '')
    const evidence = String(formData.get('evidence_id') ?? '').trim()
    body.evidence_id = evidence || null
  }
  if (move === 'approve') {
    const comments = String(formData.get('comments') ?? '').trim()
    body.comments = comments || null
  }

  const result = await moveSignal(id, move, body)

  if (!result.ok) {
    return { error: result.message }
  }

  revalidatePath(`/workspace/integrity/${id}`)
  revalidatePath('/workspace/integrity')
  return { done: DONE[move] }
}
