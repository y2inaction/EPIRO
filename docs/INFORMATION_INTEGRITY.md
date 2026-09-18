# Information integrity

Spec sections 25–26. A claim circulating in public is logged, assessed against
evidence, signed off by someone other than the assessor, and answered publicly
by someone other than the approver.

This document exists mainly to record what the feature deliberately **cannot**
do, because that is the part a later contributor is most likely to undo by
accident.

---

## 1. The record is about information, not people

Spec section 4 forbids voter profiling, political preference inference,
psychological profiling and susceptibility scoring. A misinformation feature is
where that prohibition is most likely to be broken, because the obvious next
feature is always "who is spreading this".

So the table has nowhere to put it. There is no column for an account, a
handle, an audience, a segment or a person, and `tests/test_integrity.py`
asserts that none has appeared:

```python
def test_the_model_has_nowhere_to_record_who_spread_a_claim(self):
    columns = set(IntegritySignal.__table__.columns.keys())
    assert columns & {"spreader", "account", "audience", "susceptibility_score", ...} == set()
```

`source` and `circulation` describe a **channel** — "voice notes forwarded on
WhatsApp", "a headline in a state daily". The wording on the portal is held to
the same line: `__tests__/format.test.ts` asserts that no finding's description
contains "spread by", "targeted", "audience" or "they believe".

The published record names nobody at all, reviewers included. The public
schema is an allow-list and a test pins its exact field set, so a field cannot
reach the portal by being added to the model.

## 2. A determination must be source-linked

This is the rule that makes a correction checkable rather than merely asserted.

| Finding | Meaning | Needs a cited evidence record |
|---|---|---|
| `accurate` | Checked, and the claim holds up. | Yes |
| `misleading` | Partly true, framed to give a false impression. | Yes |
| `out_of_context` | Real material, presented as being about something else. | Yes |
| `false` | Checked, and the claim does not hold up. | Yes |
| `unsubstantiated` | Nothing found that supports it. Not the same as disproved. | Yes |
| `unresolved` | Looked into, and it could not be settled either way. | **No** |

`unresolved` is the one exemption, and it is a deliberate one. It asserts
nothing about the claim, so there is nothing to source. Without it the only
approvable outcome would be a verdict — which is how unverified verdicts get
recorded. Spec section 32 forbids claiming verification that was not performed;
an honest "we looked and could not settle it" has to remain sayable.

The cited evidence must itself have cleared approval, and it is **re-checked at
publication**, because it can be withdrawn in between. A correction resting on
a record the body has since taken back must not go out on the strength of an
approval given while it still stood.

## 3. The lifecycle

```
new ──assess──▶ assessed ──approve──▶ approved ──publish──▶ published
  ▲                 │           │                               │
  │              reject      reject                         withdraw
  │ (reword)         ▼           ▼                               ▼
  └───────────── assessing ◀─────┘                           withdrawn

any state except published ──close──▶ closed
```

| Step | Role | Rules |
|---|---|---|
| Log | `INTEGRITY_MONITORS` | Observation, so it is open to field staff and researchers. |
| Assess | `INTEGRITY_ASSESSORS` | Finding and reasoning are written together; neither is optional. |
| Respond | `INTEGRITY_ASSESSORS` | The correction itself. Allowed before or after approval, never after publication. |
| Approve | `APPROVERS` | Source link required (section 2). **The assessor may not approve.** |
| Reject | `APPROVERS` | Reason required. Clears the approval and returns to assessing. |
| Publish | `PUBLISHERS` | Evidence re-checked. **The approver may not publish.** |
| Withdraw | `PUBLISHERS` | Reason required. Drops off the portal immediately. |
| Close | `INTEGRITY_MONITORS` | Not available once published — withdraw instead. |

Logging what is circulating is observation, and observation is what field staff
do. Deciding what is true about it is a narrower act, so `INTEGRITY_ASSESSORS`
is a smaller set. Both are checked against the specific organisation, as
everywhere else in the platform.

## 4. Rewording a claim throws away the finding

An assessment answers a particular form of words. Editing the claim raises the
version and returns the record to `assessing`, clearing the finding, the
assessor and any approval — the same rule evidence already follows.

Changing the priority or the owner does **not** do this. Distinguishing the two
is what stops an assessment being discarded every time somebody reassigns a
case. See `services/integrity.changes_the_claim`.

## 5. What is not built

Stated here rather than left to be discovered:

- **No public submission.** A member of the public reporting "I saw this going
  round" would be genuinely useful, and it is also a channel for reporting each
  other. Spec section 20 limits collection to what legitimate operation needs,
  so the first version keeps logging to staff.
- **No staged review.** The configurable workflows of spec section 36 are wired
  into evidence only; integrity signals use the single implicit approval stage.
- **No front-end workspace screen.** The full workflow is in the API and
  exercised end to end, but staff drive it through the API rather than a
  screen. The public side does have a front end: `/corrections`.
- **No automated detection.** Signals are logged by people. Nothing scans,
  scores or ranks anything on its own, which also means nothing here can
  silently become a monitoring system.

## 6. The public record

Published corrections appear at `/api/v1/public/corrections` and on the portal
at `/corrections`, with no authentication.

Each one carries the claim, the finding, **the reasoning**, the body's response
and a link to the evidence. Publishing the verdict without the reasoning would
make the platform a source of pronouncements rather than of checkable
information — the reasoning is the part that lets a reader disagree with it.

Repeating a false claim in order to correct it is the standing difficulty of
any such page. Two things are done about it: the claim is always marked up and
introduced as a quotation so it cannot be read as the body's own statement, and
the page title leads with the finding rather than the claim, so a share preview
that never shows the body does not amount to the claim republished under the
platform's name.
