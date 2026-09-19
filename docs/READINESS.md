# Readiness and scenarios

Spec sections 28–31. A scenario is something the organisation must be ready
for. Its readiness colour is the most quotable thing this platform produces —
"we are GREEN on flood response" is a sentence somebody repeats in a briefing —
and unlike a story or a correction it has no evidence attached to it by
construction.

So there is one rule, and the rest of this document is its consequences.

> **A status may be declared as bad as you like, and no better than the record
> supports.**

---

## 1. The floor

The floor is the best colour a scenario's record supports. It is computed, not
stored, from four things the system already knows.

| What is missing | Floor |
|---|---|
| No playbook at all | **RED** — there is nothing to rehearse and nothing to follow on the day |
| A plan that has never been rehearsed | **AMBER** — untested |
| A rehearsal older than the scenario's drill interval | **AMBER** — no longer current |
| A critical drill finding still open | **AMBER** — a known gap that would stop the response working |
| None of the above | **GREEN** |

`GET /api/v1/scenarios/{id}` returns the floor alongside the declared status on
every read, with the reasons spelled out, so nobody has to ask a second
question to find out whether a colour is backed by anything.

A reason is phrased as the work required rather than as a grade: "The scenario
has never been rehearsed, so the plan is untested", not "insufficient".

## 2. What the floor does and does not do

**It caps declarations upward.** `POST /scenarios/{id}/declare` refuses a status
better than the floor and says which gap is in the way.

**It does not cap them downward.** An owner may declare BLACK on a scenario
whose floor is GREEN. They may know the only trained coordinator resigned this
week, and none of that is in the database. Judgement in the pessimistic
direction is exactly what a human declaration is for.

**No role is exempt** — a platform administrator included. This is the same
reason separation of duties is not waived for a super admin: a privilege that
could switch the cap off would make the matrix worthless, and the matrix is
the product.

**It never improves a status by itself.** Completing a drill can lift the
floor, but the declared status stays where it was until a person moves it and
says why. A machine must not quietly raise a claim that somebody else will be
held to.

## 3. A scenario starts RED

There is no status field on the create request. A new scenario has no plan and
no rehearsal, so the worst honest answer is the only available one. Letting a
creator open a record already marked GREEN is the hole the whole feature exists
to close.

Declaring GREEN is an act somebody performs and signs. It is not where a record
begins.

## 4. Playbooks

A playbook is an ordered list of steps, each of which **must name a responsible
role**. A plan that does not say whose job something is, is not a plan, so the
schema cannot express one. `within_hours` is optional but is what makes a
rehearsal checkable: without a stated expectation there is nothing for a drill
to find wanting.

Steps must be numbered 1..n with no gaps or repeats. A plan that is ambiguous
about what happens after step 3 fails at the one thing a plan is for.

The playbook is replaced whole rather than edited step by step, because the
steps are ordered and a per-step edit would leave the ordering briefly
meaningless.

`playbook_url` still exists for an external plan document. It is not a
substitute for the steps: a URL cannot be checked for whether it says who does
what.

## 5. Drills

```
scheduled ──complete──▶ completed
    │
  cancel
    ▼
cancelled
```

A completed drill **requires a summary**. The previous design had a single
`last_drill_date` column and nothing else — a rehearsal whose findings are not
written down is indistinguishable from one that never happened, and a date was
being read as readiness.

`last_drill_date` is now derived from completed drill records, so the date and
the account of what happened cannot disagree.

Cancelled drills stay on the record with their reason. A scenario whose
rehearsals keep being called off is exactly the one a readiness review should
be able to see — and without this, scheduling and cancelling would be a way to
launder a scenario towards green.

## 6. Findings, and who may close them

A drill finding describes **what the response could not do**. Spec section 4's
prohibition on profiling is not only about citizens, and a rehearsal is the
obvious place a blame column would otherwise appear. There is none, and a test
asserts that none has been added.

Severity runs observation → minor → major → **critical**. Only critical holds
the floor down; the rest are recorded without capping the colour.

**A finding is confirmed resolved by someone other than the person who raised
it.** The finder may well be the one who does the fixing; somebody else has to
be the one who says it is fixed. Without this, "I found a problem in my own
drill and I say I fixed it" would lift the readiness cap on one person's word,
which is the self-certification the rest of the platform refuses.

## 7. Roles

| Act | Roles |
|---|---|
| Register, edit, write a playbook, schedule or cancel a drill, declare readiness | `READINESS_MANAGERS` — executive, analyst |
| Complete a drill, resolve a finding | `DRILL_CONDUCTORS` — executive, analyst, field officer, evidence manager |

Declaring how ready a body is, is an executive act, so that set is small.
Rehearsing is not: the people who would have to carry out a plan are the ones
who can tell whether it works, so conducting a drill is open wider.

## 8. Readiness is not public

This is a decision, not an omission.

Publishing that a body is RED on flood response tells the public something true
and useful, and tells anyone who would exploit the gap exactly where it is.
Spec section 20 limits collection to legitimate operational purposes, and the
same caution applies to disclosure. The first version keeps the matrix
internal, scoped to the organisations a caller belongs to.

If that changes, the thing to publish is the floor and its reasons rather than
the declared colour alone — the reasons are the part a reader could check.

## 9. What is not built

- **No front end.** The workflow is complete in the API and exercised end to
  end, but there is no readiness screen. See `docs/STATUS.md`.
- **No notifications.** Nothing tells an owner that a drill has fallen out of
  date; the floor reports it on read, but only when somebody looks.
- **No cross-scenario rollup.** There is no organisation-level readiness
  figure, deliberately: averaging four scenarios into one colour would discard
  exactly the detail that makes the matrix useful.
- **No link from a scenario to the evidence behind it.** A scenario is an
  operational plan rather than a public claim, so the fact-base rule that
  governs stories and corrections does not apply to it.
