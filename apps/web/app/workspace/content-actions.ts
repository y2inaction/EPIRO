'use server'

import { revalidatePath } from 'next/cache'

import type { QuestionActionName, StoryActionName } from '@/lib/transitions'
import {
  approveQuestion,
  approveStory,
  publishQuestion,
  publishStory,
  rejectQuestion,
  rejectStory,
  respondToQuestion,
  submitStory,
  triageQuestion,
  withdrawStory,
} from '@/lib/workspace'

export interface TransitionState {
  error?: string
  done?: string
}

const STORY_DONE: Record<StoryActionName, string> = {
  submit: 'Submitted. A reviewer will pick it up.',
  approve: 'Approved. Someone else publishes it.',
  reject: 'Sent back with your reason, and recorded on the approval trail.',
  publish: 'Published to the public portal.',
  withdraw: 'Withdrawn. The story stays, marked as retracted.',
}

const QUESTION_DONE: Record<QuestionActionName, string> = {
  triage: 'Claimed. It can now be answered.',
  respond: 'Answer drafted. It needs approval before it is published.',
  approve: 'Approved. Someone else publishes it.',
  reject: 'Sent back for more research, with your reason.',
  publish: 'Published on the public portal.',
}

/** A reason is required before the round trip, so a person is told sooner. */
function missingReason(action: string, reason: string): boolean {
  return ['reject', 'withdraw', 'respond'].includes(action) && !reason
}

export async function applyStoryTransition(
  _state: TransitionState,
  formData: FormData,
): Promise<TransitionState> {
  const id = String(formData.get('story_id') ?? '')
  const action = String(formData.get('action') ?? '') as StoryActionName
  const reason = String(formData.get('reason') ?? '').trim()
  const changesRequested = formData.get('changes_requested') === 'on'

  if (!id) {
    return { error: 'No story was named.' }
  }
  if (missingReason(action, reason)) {
    return { error: 'Give a reason. The author needs to know what to change.' }
  }

  let result
  switch (action) {
    case 'submit':
      result = await submitStory(id)
      break
    case 'approve':
      result = await approveStory(id, reason || undefined)
      break
    case 'reject':
      result = await rejectStory(id, reason, changesRequested)
      break
    case 'publish':
      result = await publishStory(id)
      break
    case 'withdraw':
      result = await withdrawStory(id, reason)
      break
    default:
      return { error: 'That is not an action on this story.' }
  }

  if (!result.ok) {
    return { error: result.message }
  }

  revalidatePath(`/workspace/stories/${id}`)
  revalidatePath('/workspace/stories')
  return { done: STORY_DONE[action] }
}

export async function applyQuestionTransition(
  _state: TransitionState,
  formData: FormData,
): Promise<TransitionState> {
  const id = String(formData.get('question_id') ?? '')
  const action = String(formData.get('action') ?? '') as QuestionActionName
  const reason = String(formData.get('reason') ?? '').trim()
  const organisationId = String(formData.get('organisation_id') ?? '')
  const changesRequested = formData.get('changes_requested') === 'on'

  if (!id) {
    return { error: 'No question was named.' }
  }
  if (action === 'respond' && !reason) {
    return { error: 'Write the answer before submitting it.' }
  }
  if (missingReason(action, reason)) {
    return { error: 'Give a reason, so whoever picks this up knows what to do.' }
  }

  let result
  switch (action) {
    case 'triage':
      if (!organisationId) {
        return { error: 'Choose which organisation will answer this.' }
      }
      result = await triageQuestion(id, organisationId)
      break
    case 'respond':
      result = await respondToQuestion(id, reason)
      break
    case 'approve':
      result = await approveQuestion(id, reason || undefined)
      break
    case 'reject':
      result = await rejectQuestion(id, reason, changesRequested)
      break
    case 'publish':
      result = await publishQuestion(id)
      break
    default:
      return { error: 'That is not an action on this question.' }
  }

  if (!result.ok) {
    return { error: result.message }
  }

  revalidatePath(`/workspace/questions/${id}`)
  revalidatePath('/workspace/questions')
  return { done: QUESTION_DONE[action] }
}
