import {
  questionActions,
  questionWaitingFor,
  storyActions,
  storyWaitingFor,
} from '@/lib/transitions'

function storyNames(status: string, role: string | undefined): string[] {
  return storyActions({ status }, role).map((a) => a.name)
}

function questionNames(
  status: string,
  role: string | undefined,
  response: string | null = null,
): string[] {
  return questionActions({ status, response }, role).map((a) => a.name)
}

describe('storyActions', () => {
  it('lets an author submit a draft', () => {
    expect(storyNames('draft', 'content_manager')).toContain('submit')
  })

  it('lets an author resubmit something that was sent back', () => {
    expect(storyNames('rejected', 'content_manager')).toContain('submit')
  })

  it('does not let an approver submit on the author’s behalf', () => {
    expect(storyNames('draft', 'approver')).not.toContain('submit')
  })

  it('offers approval only while a story is under review', () => {
    expect(storyNames('in_review', 'approver')).toContain('approve')
    expect(storyNames('draft', 'approver')).not.toContain('approve')
    expect(storyNames('approved', 'approver')).not.toContain('approve')
  })

  it('does not offer publication to the approver role', () => {
    // Approval and release are two decisions by two people.
    expect(storyNames('approved', 'approver')).not.toContain('publish')
    expect(storyNames('approved', 'content_manager')).toContain('publish')
  })

  it('offers an editor both approval and publication, because they hold both roles', () => {
    // The interface offers both; the server still refuses the same person
    // doing both on one story. This asserts the offer, not the permission.
    expect(storyNames('in_review', 'editor')).toContain('approve')
    expect(storyNames('approved', 'editor')).toContain('publish')
  })

  it('replaces rejection with withdrawal once published', () => {
    const published = storyNames('published', 'content_manager')

    expect(published).toContain('withdraw')
    expect(published).not.toContain('reject')
  })

  it('offers nothing on an archived story', () => {
    expect(storyNames('archived', 'content_manager')).toEqual([])
    expect(storyNames('archived', 'approver')).toEqual([])
  })

  it('requires a reason to send back or withdraw', () => {
    const sendBack = storyActions({ status: 'in_review' }, 'approver').find(
      (a) => a.name === 'reject',
    )
    const withdraw = storyActions({ status: 'published' }, 'content_manager').find(
      (a) => a.name === 'withdraw',
    )

    expect(sendBack?.requiresReason).toBe(true)
    expect(withdraw?.requiresReason).toBe(true)
  })

  it('offers nothing to someone with no role', () => {
    expect(storyNames('in_review', undefined)).toEqual([])
  })
})

describe('storyWaitingFor', () => {
  it('names the separation at each stage', () => {
    expect(storyWaitingFor({ status: 'in_review' })).toContain('cannot be its author')
    expect(storyWaitingFor({ status: 'approved' })).toContain('cannot be the approver')
  })

  it('describes a withdrawn story', () => {
    expect(storyWaitingFor({ status: 'archived' })).toContain('Withdrawn')
  })
})

describe('questionActions', () => {
  it('offers claiming only on an unclaimed question', () => {
    expect(questionNames('new', 'researcher')).toContain('triage')
    expect(questionNames('triaged', 'researcher')).not.toContain('triage')
  })

  it('does not let an approver claim a question', () => {
    // approver is not among the question responders.
    expect(questionNames('new', 'approver')).not.toContain('triage')
  })

  it('offers drafting an answer once claimed', () => {
    expect(questionNames('triaged', 'researcher')).toContain('respond')
    expect(questionNames('researching', 'researcher')).toContain('respond')
  })

  it('labels the action differently once an answer exists', () => {
    const fresh = questionActions({ status: 'triaged', response: null }, 'researcher')
    const rewrite = questionActions(
      { status: 'response_drafted', response: 'An answer.' },
      'researcher',
    )

    expect(fresh.find((a) => a.name === 'respond')?.label).toBe('Draft an answer')
    expect(rewrite.find((a) => a.name === 'respond')?.label).toBe('Rewrite the answer')
  })

  it('always requires the answer text', () => {
    const respond = questionActions({ status: 'triaged', response: null }, 'researcher').find(
      (a) => a.name === 'respond',
    )

    expect(respond?.requiresReason).toBe(true)
  })

  it('offers approval only on a drafted answer', () => {
    expect(questionNames('response_drafted', 'approver', 'An answer.')).toContain('approve')
    expect(questionNames('triaged', 'approver')).not.toContain('approve')
  })

  it('does not offer publication to the approver role', () => {
    expect(questionNames('approved', 'approver', 'An answer.')).not.toContain('publish')
    expect(questionNames('approved', 'content_manager', 'An answer.')).toContain('publish')
  })

  it('offers nothing on a published or closed question', () => {
    expect(questionNames('published', 'content_manager', 'An answer.')).toEqual([])
    expect(questionNames('closed', 'researcher')).toEqual([])
  })

  it('offers nothing to someone with no role', () => {
    expect(questionNames('new', undefined)).toEqual([])
  })
})

describe('questionWaitingFor', () => {
  it('says nobody has claimed a new question', () => {
    expect(questionWaitingFor({ status: 'new', response: null })).toContain('claimed')
  })

  it('names the separation of duties on a drafted answer', () => {
    expect(questionWaitingFor({ status: 'response_drafted', response: 'x' })).toContain(
      'cannot have drafted it',
    )
  })

  it('describes a closed question', () => {
    expect(questionWaitingFor({ status: 'closed', response: null })).toContain('Closed')
  })
})
