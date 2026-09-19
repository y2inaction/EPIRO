# Approval workflows

Spec section 36 requires that an approval be **recorded**, storing reviewer,
timestamp, decision, comments and version, and that workflows be
**configurable**.

Both are now CONFIRMED, with one limit stated plainly in section 7: an
organisation configures the **review stages**, not the lifecycle around them.

---

## 1. The approval trail

One table, `approval_record`, serves every content type. It is addressed by
`(entity_type, entity_id)` rather than by a foreign key per kind, so evidence,
stories, questions and integrity findings share one trail instead of each
growing its own set of approval columns.

| Column | Purpose |
|---|---|
| `entity_type`, `entity_id` | What was decided on. |
| `entity_version` | The version the decision covered. |
| `decision` | `approved`, `rejected` or `changes_requested`. |
| `reviewer_id` | Who decided. |
| `decided_at` | When. |
| `comments` | Why. Required on a rejection. |

**Every round is kept, including the ones that refused.** The previous design
stored only the latest approver id on the record itself, so a rejection left no
trace at all and `EvidenceStatus.REJECTED` was a state nothing could reach.
The history of what was turned down is as much a part of accountability as
what went through.

`entity_version` is what makes the trail meaningful. A record's version is
raised on every content edit, and an edit to something already approved
returns it to draft — so an approval can never end up describing content its
approver never saw.

## 2. Evidence

```
draft ──verify──▶ verified ──approve──▶ approved ──publish──▶ published
                     │           │                                │
                  reject      reject                          withdraw
                     ▼           ▼                                ▼
                 rejected    rejected                         archived
```

| Step | Role | Rules |
|---|---|---|
| Verify | `EVIDENCE_VERIFIERS` | — |
| Approve | `APPROVERS` | Must already be verified. **The verifier may not approve.** |
| Reject | `APPROVERS` | Reason required. Published evidence cannot be rejected — withdraw it. |
| Publish | `PUBLISHERS` | Must be approved. |
| Withdraw | `PUBLISHERS` | Reason required. Archives rather than deletes. |

Approving evidence that carries a measurement also moves its indicator's
current value — so a figure on a dashboard always traces back to an approved
record. An older measurement approved late does not overwrite a newer one.

## 3. Stories

```
draft ──submit──▶ in_review ──approve──▶ approved ──publish──▶ published
  ▲                   │                      │                      │
  │                reject                 reject                withdraw
  │ (edit)             ▼                      ▼                      ▼
  └───────────────  rejected ──submit──▶  rejected              archived
```

| Step | Role | Rules |
|---|---|---|
| Submit | `CONTENT_AUTHORS` | From draft or rejected. |
| Approve | `STORY_APPROVERS` | **The author may not approve.** The supporting evidence must itself be approved. |
| Reject | `STORY_APPROVERS` | Reason required. Clears any existing approval. |
| Publish | `PUBLISHERS` | **The approver may not publish, and neither may the author.** Evidence is re-checked, because it can be withdrawn between approval and publication. |
| Withdraw | `PUBLISHERS` | Reason required. Also drops the story from the featured set. |

Publication used to be a single call that set the approver, the approval date
and the publication date together — whoever pressed publish *was* the
approval, so nothing ever separated signing off public information from
releasing it.

## 4. Questions

```
new ──triage──▶ triaged ──respond──▶ response_drafted ──approve──▶ approved ──publish──▶ published
                   ▲                        │                          │
                   │                     reject                     reject
                   └── researching ◀────────┴──────────────────────────┘
```

| Step | Role | Rules |
|---|---|---|
| Triage | `QUESTION_RESPONDERS` **in the receiving organisation** | Assigns the question to a body. |
| Respond | `QUESTION_RESPONDERS` | Answer carried in the request body. |
| Approve | `APPROVERS` | **The person who drafted the answer may not approve it.** |
| Reject | `APPROVERS` | Reason required. Returns to research and clears any approval. |
| Publish | `PUBLISHERS` | **The approver may not publish.** |
| Close | `QUESTION_RESPONDERS` | No further responses. |

Triage is the only step whose role is checked against an organisation the
record does not yet belong to. It has to be: a publicly submitted question
belongs to nobody until someone claims it, so there is no tenant to check
against. Without this step every public question was permanently stuck.

## 5. Integrity findings

```
new ──assess──▶ assessed ──approve──▶ approved ──publish──▶ published
  ▲                 │           │                               │
  │ (reword)     reject      reject                         withdraw
  └───────────── assessing ◀─────┘                               ▼
                                                             withdrawn
```

| Step | Role | Rules |
|---|---|---|
| Assess | `INTEGRITY_ASSESSORS` | Finding and reasoning are written together. |
| Approve | `APPROVERS` | Must cite approved evidence (see section 6). **The assessor may not approve.** |
| Reject | `APPROVERS` | Reason required. Clears the approval. |
| Publish | `PUBLISHERS` | Evidence re-checked. **The approver may not publish.** |
| Withdraw | `PUBLISHERS` | Reason required. Leaves the portal at once. |

Rewording the claim raises the version and clears the finding, because the
finding answered the old wording. Re-prioritising does not.

Full detail, including what the feature deliberately cannot do, is in
[INFORMATION_INTEGRITY.md](INFORMATION_INTEGRITY.md).

## 6. The one fact base rule

Nothing goes public that is not traceable to approved evidence.

- A story cannot be approved unless its evidence is approved or published.
- A story cannot be published if its evidence was withdrawn in the meantime.
- A published story carries the permanent reference of its evidence, so a
  reader can follow the claim back to the record it rests on.
- An integrity finding cannot be approved unless it cites approved evidence.
  The single exception is a finding of `unresolved`, which asserts nothing
  about the claim and so has nothing to source — without it the only
  approvable outcome would be a verdict, which is how unverified verdicts get
  recorded.

## 7. Configurable review stages

An organisation defines the sequence of review stages its content must clear
before it counts as approved, through `/api/v1/workflows`. Spec section 36's
own example — Draft → Review → Fact Check → Compliance → Approval →
Publication — is exactly that shape: every configurable step in it sits
between submission and publication.

```
POST /api/v1/workflows
{
  "organisation_id": "...",
  "entity_type": "evidence",
  "name": "Editorial review",
  "stages": [
    {"name": "Fact check",  "required_roles": ["verifier"]},
    {"name": "Compliance",  "required_roles": ["executive"]},
    {"name": "Approval",    "required_roles": ["approver"]}
  ]
}
```

Each `POST /evidence/{id}/approve` then clears one stage. The record becomes
approved only when the last is cleared, and each cleared stage is named on the
approval trail. A rejection sends the record back to the first stage, because
whatever was cleared was cleared against content that has since been sent
back. An edit does the same, by raising the version.

Progress is **derived from the approval trail**, not stored on the record. A
pointer would be a second copy of something the trail already knows, and the
copy is what drifts.

Where a stage is configured, the roles it names are the authority on who may
clear it — choosing who reviews is the point of configuring a workflow, so the
endpoint's own default must not override it. An organisation that has
configured nothing keeps the default exactly.

### What an organisation cannot configure

This is the part that matters, and an earlier version of this document got it
wrong. It said a current-stage pointer should *replace the fixed status
enums*. That would have been a mistake: the public portal's "published" filter
would then read a configurable pointer, and an organisation could change what
"published" means to the public by editing its own configuration — the same
accountability hole the final-stage rule below guards against, reached from
the other side.

So the coarse lifecycle — draft, approved, published, withdrawn — stays fixed
in code. Configurability must not reach the guarantees the platform makes to
people outside it.

Refused at definition time:

| Attempted | Refused because |
|---|---|
| A workflow with no stages | Nothing would ever be reviewed. |
| A stage naming no role | Nothing could ever clear it. |
| A stage naming an unknown role | It could never be satisfied. |
| A stage naming `public_user` | Review is what the organisation is accountable for, not the public. |
| A final stage not requiring a distinct actor | One person would be the only review before publication. |

The last row is the one to keep. An organisation may add rigour; it may not
remove it. A configuration switch that turned off the separation of duties
would make the platform's central claim false.
