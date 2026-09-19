import { offersFor, waitingFor } from '@/lib/decisions'

describe('offersFor', () => {
  it('offers only what the lifecycle allows from here', () => {
    // Mirrors app/services/actions.py. Offering a button that always fails
    // wastes somebody's time and makes the system look broken.
    expect(offersFor('proposed').map((o) => o.name)).toEqual(['accept', 'drop'])
    expect(offersFor('accepted').map((o) => o.name)).toEqual(['start', 'drop'])
    expect(offersFor('in_progress').map((o) => o.name)).toEqual(['complete', 'drop'])
  })

  it('offers nothing on a closed decision, which is never reopened', () => {
    expect(offersFor('done')).toEqual([])
    expect(offersFor('dropped')).toEqual([])
  })

  it('offers nothing for a state it does not recognise, rather than guessing', () => {
    expect(offersFor('invented')).toEqual([])
  })

  it('requires an outcome exactly where the server does', () => {
    const needing = ['proposed', 'accepted', 'in_progress']
      .flatMap(offersFor)
      .filter((o) => o.needsOutcome)
      .map((o) => o.name)

    expect(new Set(needing)).toEqual(new Set(['complete', 'drop']))
  })
})

describe('waitingFor', () => {
  it('distinguishes finished from decided against', () => {
    expect(waitingFor('done', false)).toContain('Carried out')
    expect(waitingFor('dropped', false)).toContain('Decided against')
  })

  it('says when an open action is late', () => {
    expect(waitingFor('accepted', true)).toContain('Past its date')
  })

  it('never returns nothing, because a blank reads as a missing permission', () => {
    for (const status of ['proposed', 'accepted', 'in_progress', 'done', 'dropped']) {
      expect(waitingFor(status, false).length).toBeGreaterThan(0)
    }
  })
})

import { ORIGIN_SOURCES, parseOrigin } from '@/lib/decisions'

describe('parseOrigin', () => {
  it('splits the picker value into the type and the id', () => {
    expect(parseOrigin('integrity_signal:abc-123')).toEqual({
      originType: 'integrity_signal',
      originId: 'abc-123',
    })
  })

  it('keeps an id that contains a colon intact', () => {
    // Split on the first separator only. Splitting on every colon would
    // truncate the id and cite a record that does not exist.
    expect(parseOrigin('evidence:a:b')).toEqual({ originType: 'evidence', originId: 'a:b' })
  })

  it('refuses a type it does not offer, rather than passing it through', () => {
    expect(parseOrigin('voter_profile:abc')).toBeNull()
  })

  it('refuses anything malformed rather than guessing', () => {
    // An action with a mis-parsed origin cites the wrong record, which is
    // worse than a refusal.
    expect(parseOrigin('')).toBeNull()
    expect(parseOrigin('evidence')).toBeNull()
    expect(parseOrigin('evidence:')).toBeNull()
    expect(parseOrigin(':abc')).toBeNull()
  })
})

describe('ORIGIN_SOURCES', () => {
  it('offers only origins the server accepts', () => {
    // Mirrors ORIGIN_MODELS in app/services/actions.py. drill_finding is
    // absent on purpose: it is not an intelligence measure, so there is no
    // list to draw candidates from.
    expect(ORIGIN_SOURCES.map((s) => s.originType)).toEqual([
      'integrity_signal',
      'scenario',
      'evidence',
    ])
  })
})
