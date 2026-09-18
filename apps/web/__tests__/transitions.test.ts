import { holds, roleIn, type CurrentUser } from '@/lib/session'
import { availableActions, waitingFor } from '@/lib/transitions'
import type { Evidence } from '@/lib/workspace'

const BASE: Evidence = {
  id: 'evidence-1',
  reference: 'EV-2026-000001',
  title: 'Borehole handover record',
  description: null,
  outcome: null,
  evidence_date: '2026-06-01',
  beneficiaries: null,
  organisation_id: 'org-1',
  source_id: 'source-1',
  status: 'draft',
  verification_status: 'unverified',
  approval_status: 'pending',
  version: 1,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
}

function evidence(overrides: Partial<Evidence> = {}): Evidence {
  return { ...BASE, ...overrides }
}

function names(record: Evidence, role: string | undefined): string[] {
  return availableActions(record, { id: 'me', role }).map((a) => a.name)
}

describe('holds', () => {
  it('matches a listed role', () => {
    expect(holds('verifier', ['verifier', 'evidence_manager'])).toBe(true)
  })

  it('refuses a role that is not listed', () => {
    expect(holds('researcher', ['verifier'])).toBe(false)
  })

  it('gives super_admin every right within its own organisation', () => {
    expect(holds('super_admin', ['verifier'])).toBe(true)
  })

  it('refuses when there is no role at all', () => {
    // A user with no membership in this organisation.
    expect(holds(undefined, ['verifier'])).toBe(false)
  })
})

describe('roleIn', () => {
  it('finds the role for the named organisation', () => {
    const user: CurrentUser = {
      id: 'u1',
      email: 'a@example.com',
      first_name: 'A',
      last_name: 'B',
      memberships: [
        { organisation_id: 'org-1', name: 'One', code: 'one', role: 'verifier' },
        { organisation_id: 'org-2', name: 'Two', code: 'two', role: 'approver' },
      ],
    }

    expect(roleIn(user, 'org-1')).toBe('verifier')
    expect(roleIn(user, 'org-2')).toBe('approver')
    expect(roleIn(user, 'org-3')).toBeUndefined()
  })
})

describe('availableActions', () => {
  it('offers verification on an unverified record to a verifier', () => {
    expect(names(evidence(), 'verifier')).toContain('verify')
  })

  it('offers nothing to someone with no role here', () => {
    expect(names(evidence(), undefined)).toEqual([])
  })

  it('does not offer verification to a researcher', () => {
    expect(names(evidence(), 'researcher')).toEqual([])
  })

  it('does not offer approval before verification', () => {
    // The API refuses it; offering the button would only waste a round trip.
    expect(names(evidence(), 'approver')).not.toContain('approve')
  })

  it('offers approval once a record is verified', () => {
    const verified = evidence({ verification_status: 'verified', status: 'verified' })

    expect(names(verified, 'approver')).toContain('approve')
  })

  it('does not offer approval twice', () => {
    const approved = evidence({
      verification_status: 'verified',
      approval_status: 'approved',
      status: 'approved',
    })

    expect(names(approved, 'approver')).not.toContain('approve')
  })

  it('offers rejection at any point before publication', () => {
    expect(names(evidence(), 'approver')).toContain('reject')
    expect(names(evidence({ verification_status: 'verified' }), 'approver')).toContain('reject')
    expect(
      names(
        evidence({ verification_status: 'verified', approval_status: 'approved' }),
        'approver',
      ),
    ).toContain('reject')
  })

  it('offers publication only once approved, and only to a publisher', () => {
    const approved = evidence({
      verification_status: 'verified',
      approval_status: 'approved',
      status: 'approved',
    })

    expect(names(approved, 'content_manager')).toContain('publish')
    expect(names(approved, 'approver')).not.toContain('publish')
    expect(names(evidence(), 'content_manager')).not.toContain('publish')
  })

  it('offers withdrawal instead of rejection once published', () => {
    const published = evidence({
      status: 'published',
      verification_status: 'verified',
      approval_status: 'approved',
    })

    const offered = names(published, 'content_manager')
    expect(offered).toContain('withdraw')
    expect(offered).not.toContain('reject')
    expect(offered).not.toContain('publish')
  })

  it('offers nothing on a published record to an approver', () => {
    const published = evidence({
      status: 'published',
      verification_status: 'verified',
      approval_status: 'approved',
    })

    expect(names(published, 'approver')).toEqual([])
  })

  it('requires a written reason for rejection and withdrawal, and not otherwise', () => {
    const actions = availableActions(
      evidence({ verification_status: 'verified' }),
      { id: 'me', role: 'super_admin' },
    )
    const byName = Object.fromEntries(actions.map((a) => [a.name, a.requiresReason]))

    expect(byName.reject).toBe(true)
    expect(byName.approve).toBe(false)
  })

  it('marks rejection and withdrawal as destructive so they are not styled as the default', () => {
    const actions = availableActions(evidence(), { id: 'me', role: 'approver' })

    expect(actions.find((a) => a.name === 'reject')?.destructive).toBe(true)
  })
})

describe('waitingFor', () => {
  it('says a record is waiting on a verifier', () => {
    expect(waitingFor(evidence())).toContain('verifier')
  })

  it('names the separation of duties once verified', () => {
    const verified = evidence({ verification_status: 'verified' })

    expect(waitingFor(verified)).toContain('other than the verifier')
  })

  it('says a record is waiting on a publisher once approved', () => {
    const approved = evidence({
      verification_status: 'verified',
      approval_status: 'approved',
    })

    expect(waitingFor(approved)).toContain('publisher')
  })

  it('describes a published record', () => {
    expect(waitingFor(evidence({ status: 'published' }))).toContain('Published')
  })

  it('describes a rejected record as the author’s to revise', () => {
    expect(waitingFor(evidence({ status: 'rejected' }))).toContain('author')
  })
})
