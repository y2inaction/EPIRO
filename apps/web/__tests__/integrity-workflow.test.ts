import { FINDINGS, offersFor, waitingFor, type Signal } from '@/lib/integrity'

function signal(overrides: Partial<Signal> = {}): Signal {
  return {
    id: 's1',
    organisation_id: 'org-1',
    claim: 'The borehole programme was cancelled.',
    source: 'Voice notes forwarded on WhatsApp',
    circulation: null,
    first_observed: '2026-06-02',
    language: 'en',
    status: 'assessed',
    priority: 'low_risk',
    finding: 'false',
    assessment: 'The works register shows it running.',
    impact: null,
    response: null,
    evidence_id: null,
    published_at: null,
    version: 1,
    created_at: '2026-06-02T00:00:00Z',
    updated_at: '2026-06-02T00:00:00Z',
    ...overrides,
  }
}

describe('offersFor', () => {
  it('offers only what the lifecycle allows from each state', () => {
    // Mirrors app/api/integrity.py. Offering a move the server refuses
    // wastes somebody's time and makes the system look broken.
    expect(offersFor('new').map((o) => o.name)).toEqual(['assess', 'respond'])
    expect(offersFor('assessed').map((o) => o.name)).toEqual([
      'assess',
      'respond',
      'approve',
      'reject',
    ])
    expect(offersFor('approved').map((o) => o.name)).toEqual(['respond', 'reject', 'publish'])
    expect(offersFor('published').map((o) => o.name)).toEqual(['withdraw'])
  })

  it('offers nothing once a signal is withdrawn or closed', () => {
    expect(offersFor('withdrawn')).toEqual([])
    expect(offersFor('closed')).toEqual([])
  })

  it('never offers redrafting the correction after publication', () => {
    // Changing it then would rewrite what the public was told.
    expect(offersFor('published').map((o) => o.name)).not.toContain('respond')
  })

  it('offers nothing for a state it does not recognise, rather than guessing', () => {
    expect(offersFor('invented')).toEqual([])
  })

  it('asks for the finding and the reasoning together', () => {
    // A verdict with no reasoning is the unexplainable intelligence section 4
    // rules out, and the request schema cannot express one.
    const assess = offersFor('new').find((o) => o.name === 'assess')

    expect(assess?.needsFinding).toBe(true)
    expect(assess?.field?.name).toBe('assessment')
  })
})

describe('waitingFor', () => {
  it('says sign-off will be refused while the finding cites nothing', () => {
    expect(waitingFor(signal({ status: 'assessed', evidence_id: null }))).toContain(
      'cites approved evidence',
    )
  })

  it('treats unresolved as the one finding exempt from citation', () => {
    // It asserts nothing to source, so there is nothing to cite.
    const text = waitingFor(signal({ status: 'assessed', finding: 'unresolved' }))

    expect(text).toContain('other than the assessor')
    expect(text).not.toContain('cites approved evidence')
  })

  it('distinguishes approved-and-drafted from approved-and-not', () => {
    expect(waitingFor(signal({ status: 'approved', response: null }))).toContain(
      'has to be drafted',
    )
    expect(waitingFor(signal({ status: 'approved', response: 'We corrected it.' }))).toContain(
      'other than the approver',
    )
  })

  it('never returns nothing, because a blank reads as a missing permission', () => {
    for (const status of ['new', 'assessing', 'assessed', 'approved', 'published', 'withdrawn', 'closed']) {
      expect(waitingFor(signal({ status })).length).toBeGreaterThan(0)
    }
  })
})

describe('FINDINGS', () => {
  it('matches the findings the API accepts', () => {
    expect([...FINDINGS]).toEqual([
      'accurate',
      'misleading',
      'out_of_context',
      'false',
      'unsubstantiated',
      'unresolved',
    ])
  })

  it('offers no finding that describes a person rather than the claim', () => {
    // Section 4: the record is about information; whoever repeated it is not
    // the platform's business.
    for (const finding of FINDINGS) {
      expect(finding).not.toMatch(/spread|target|audience|account/)
    }
  })
})
