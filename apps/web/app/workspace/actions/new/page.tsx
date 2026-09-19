import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { RaiseDecisionForm, type OriginGroup } from '@/components/RaiseDecisionForm'
import { Notice, PageHeading } from '@/components/Shell'
import { ORIGIN_SOURCES } from '@/lib/decisions'
import { describeRecord } from '@/lib/intelligence'
import { getCurrentUser, getRecords } from '@/lib/workspace'

export const metadata: Metadata = {
  title: 'Raise a decision',
}

/**
 * Raise an action against something the organisation already holds.
 *
 * The candidates come from the intelligence drill-down, which already lists
 * every record of a measure scoped as the dashboard is — one way to
 * enumerate the rows rather than a second that could disagree with it.
 */
export default async function RaiseDecisionPage() {
  const me = await getCurrentUser()
  if (!me.ok) {
    redirect('/sign-in')
  }

  const user = me.value

  if (user.memberships.length === 0) {
    return (
      <>
        <PageHeading title="Raise a decision" />
        <Notice
          title="You do not belong to an organisation yet"
          detail="An action is raised inside a body, against something that body holds."
        />
      </>
    )
  }

  const organisation = user.memberships[0]

  const lists = await Promise.all(
    ORIGIN_SOURCES.map((source) =>
      getRecords({ measure: source.measure, organisation_id: organisation.organisation_id }, 1, 50),
    ),
  )

  const groups: OriginGroup[] = ORIGIN_SOURCES.map((source, index) => {
    const result = lists[index]
    return {
      label: source.label,
      options: !result.ok
        ? []
        : result.value.data.map((row) => {
            const summary = describeRecord(source.measure, row)
            return {
              value: `${source.originType}:${summary.id}`,
              // Trimmed: a claim can be five thousand characters and a
              // select option cannot.
              label: summary.title.length > 80 ? `${summary.title.slice(0, 79)}…` : summary.title,
            }
          }),
    }
  })

  return (
    <>
      <PageHeading
        title="Raise a decision"
        description="What the organisation will do about something it knows, and why that follows."
      />

      <RaiseDecisionForm
        organisationId={organisation.organisation_id}
        ownerId={user.id}
        ownerName={`${user.first_name} ${user.last_name}`}
        groups={groups}
      />

      <p className="mt-8">
        <Link
          href="/workspace/actions"
          className={
            'text-sm text-slate-700 underline-offset-4 hover:underline ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ' +
            'focus-visible:outline-sky-600 dark:text-slate-300'
          }
        >
          ← Back to the register
        </Link>
      </p>
    </>
  )
}
