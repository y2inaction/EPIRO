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
